import persistent_dict

import base64
from datetime import datetime
import collections
import glob
from hachoir_metadata import extractMetadata
from hachoir_parser import guessParser
from hachoir_core.stream import StringInputStream
from hachoir_core import config as hachoir_config
import itertools
import json
import md5
import os
import requests
import urlparse

hachoir_config.quiet = True

Details = collections.namedtuple('Details', ['path', 'isdir', 'ismedia'])

DEFAULT_MEDIA_EXT = ['gif', 'jpeg', 'jpg', 'mov', 'mp4', 'png']
VIDEO_EXT = ['mov', 'mp4']


class Error(Exception):
  """Base class for all exception of this module."""


class InvalidArgumentError(Error):
  """Error raised when an invalid argument is specified."""


class RemoteDataError(Error):
  """Error raised when the remote structure is incompatible with SmugCLI."""


class SmugMugLimitsError(Error):
  """Error raised when SmugMug limits are reached (folder depth, size. etc.)"""


class UnexpectedResponseError(Error):
  """Error raised when encountering unexpected data returned by SmugMug."""


class SmugMugFS(object):
  def __init__(self, smugmug):
    self._smugmug = smugmug

    # Pre-compute some common variables.
    self._media_ext = [
      ext.lower() for ext in
      self.smugmug.config.get('media_extensions', DEFAULT_MEDIA_EXT)]

  @property
  def smugmug(self):
    return self._smugmug

  def get_root_node(self, user):
    return self._smugmug.get_root_node(user)

  def path_to_node(self, user, path):
    current_node = self.get_root_node(user)
    parts = filter(bool, path.split(os.sep))
    nodes = [current_node]
    return self._match_nodes(nodes, parts)

  def _match_nodes(self, matched_nodes, dirs):
    unmatched_dirs = collections.deque(dirs)
    for dir in dirs:
      child_nodes = matched_nodes[-1].child_nodes_by_name.get(dir)
      if not child_nodes:
        break
      if len(child_nodes) > 1:
        raise RemoteDataError(
          'Multiple remote nodes matches "%s".' % os.path.join(
            *([n.name for n in matched_nodes] + [dir])))

      matched_nodes.append(child_nodes[0])
      unmatched_dirs.popleft()
    return matched_nodes, list(unmatched_dirs)

  def get(self, url):
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
    params = urlparse.parse_qs(query)
    result = self._smugmug.get_json(path, params=params)
    print json.dumps(result, sort_keys=True, indent=2, separators=(',', ': '))

  def ignore_or_include(paths, ignore):
    files_by_folder = collections.defaultdict(list)
    for folder, file in [os.path.split(path) for path in paths]:
      files_by_folder[folder].append(file)

    for folder, files in files_by_folder.iteritems():
      if not os.path.isdir(folder or '.'):
        print 'Can\'t find folder "%s".' % folder
        return
      for file in files:
        full_path = os.path.join(folder, file)
        if not os.path.exists(full_path):
          print '"%s" doesn\'t exists.' % full_path
          return

      configs = persistent_dict.PersistentDict(os.path.join(folder, '.smugcli'))
      original_ignore = configs.get('ignore', [])
      if ignore:
        updated_ignore = list(set(original_ignore) | set(files))
      else:
        updated_ignore = list(set(original_ignore) ^ (set(files) &
                                                      set(original_ignore)))
      configs['ignore'] = updated_ignore

  def ls(self, user, path, details):
    user = user or self._smugmug.get_auth_user()
    matched_nodes, unmatched_dirs = self.path_to_node(user, path)
    if unmatched_dirs:
      print '"%s" not found in "%s".' % (
        unmatched_dirs[0], os.sep.join(m.name for m in matched_nodes))
      return

    node = matched_nodes[-1]
    nodes = ([(path, node)] if 'FileName' in node else
             [(child.name, child) for child in node.get_children()])

    for name, node in nodes:
      if details:
        print json.dumps(node.json, sort_keys=True, indent=2,
                         separators=(',', ': '))
      else:
        print name

  def make_childnode(self, node, path, params=None):
    parent, name = os.path.split(path)
    if node['Type'] != 'Folder':
      raise InvalidArgumentError(
        'Nodes can only be created in folders.\n'
        '"%s" is of type "%s".' % (parent, node['Type']))

    remote_name = name.strip()
    node_params = {
      'Name': remote_name,
      'Privacy': 'Public',
      'SortDirection': 'Ascending',
      'SortMethod': 'Name',
    }
    node_params.update(params or {})

    response = node.post('ChildNodes', data=node_params)
    if response.status_code != 201:
      raise UnexpectedResponseError(
        'Error creating node "%s".\n'
        'Server responded with status code %d: %s.' % (
          path, response.status_code, response.json()['Message']))

    node = node.get_child(remote_name)
    if not node:
      raise UnexpectedResponseError(
        'Cannot find newly created node "%s".' % path)

    if node['Type'] == 'Album':
      response = node.patch('Album', json={'SortMethod': 'DateTimeOriginal'})
      if response.status_code != 200:
        print 'Failed setting SortMethod on Album "%s".' % name
        print 'Server responded with status code %d: %s.' % (
          response.status_code, response.json()['Message'])

    return node

  def make_node(self, user, paths, create_parents, node_type, privacy):
    user = user or self._smugmug.get_auth_user()
    for path in paths:
      matched_nodes, unmatched_dirs = self.path_to_node(user, path)
      if len(unmatched_dirs) > 1 and not create_parents:
        print '"%s" not found in "%s".' % (
          unmatched_dirs[0], os.sep.join(m.name for m in matched_nodes))
        continue

      if not len(unmatched_dirs):
        print 'Path "%s" already exists.' % path
        continue

      self._create_children(matched_nodes, unmatched_dirs, node_type, privacy)

  def _create_children(
      self, matched_nodes, new_children, node_type, privacy):
    path = os.path.join(*[m.name for m in matched_nodes])

    folder_depth = len(matched_nodes) + len(new_children)
    folder_depth -= 1 if node_type == 'Album' else 0
    if folder_depth >= 7:  # matched_nodes include an extra node for the root.
      raise SmugMugLimitsError(
        'Cannot create "%s", SmugMug does not support folder more than 5 level '
        'deep.' % os.sep.join([path] + new_children))

    node = matched_nodes[-1]
    all_matched = list(matched_nodes)
    for i, part in enumerate(new_children):
      path = os.path.join(path, part)
      params = {
        'Type': node_type if i == len(new_children) - 1 else 'Folder',
        'Privacy': privacy,
      }
      print 'Creating %s "%s".' % (params['Type'], path)
      node = self.make_childnode(node, part, params)
      all_matched.append(node)

    return all_matched

  def rmdir(self, user, parents, dirs):
    user = user or self._smugmug.get_auth_user()
    for dir in dirs:
      matched_nodes, unmatched_dirs = self.path_to_node(user, dir)
      if unmatched_dirs:
        print 'Folder or album "%s" not found.' % dir
        continue

      matched_nodes.pop(0)
      while matched_nodes:
        current_dir = os.sep.join(m.name for m in matched_nodes)
        node = matched_nodes.pop()
        if len(node.get_children({'count': 1})):
          print 'Cannot delete %s: "%s" is not empty.' % (
            node['Type'], current_dir)
          break

        print 'Deleting "%s".' % current_dir
        node.delete()

        if not parents:
          break

  def _ask(self, question):
    answer = raw_input(question)
    return answer.lower() in ['y', 'yes']

  def rm(self, user, force, recursive, paths):
    user = user or self._smugmug.get_auth_user()
    for path in paths:
      matched_nodes, unmatched_dirs = self.path_to_node(user, path)
      if unmatched_dirs:
        print '"%s" not found.' % path
        continue

      node = matched_nodes[-1]
      if recursive or len(node.get_children({'count': 1})) == 0:
        if force or self._ask('Remove %s node "%s"? ' % (node['Type'], path)):
          print 'Removing "%s".' % path
          node.delete()
      else:
        print 'Folder "%s" is not empty.' % path

  def upload(self, user, filenames, album):
    user = user or self._smugmug.get_auth_user()
    matched_nodes, unmatched_dirs = self.path_to_node(user, album)
    if unmatched_dirs:
      print 'Album not found: "%s".' % album
      return

    node = matched_nodes[-1]
    if node['Type'] != 'Album':
      print 'Cannot upload images in node of type "%s".' % node['Type']
      return

    child_nodes = node.child_nodes_by_name

    for filename in itertools.chain(*(glob.glob(f) for f in filenames)):
      file_basename = os.path.basename(filename).strip()
      if file_basename in child_nodes:
        print 'Skipping "%s", file already exists in Album "%s".' % (filename,
                                                                     album)
        continue

      print 'Uploading "%s" to "%s"...' % (filename, album)
      response = node.upload('Album',
                             file_basename,
                             open(filename, 'rb').read())
      if response.status_code != requests.codes.ok:
        print 'Error uploading "%s" to "%s".' % (filename, album)
        print 'Server responded with %s.' % str(response)
        return None

  def _get_common_path(self, matched_nodes, local_dirs):
    new_matched_nodes = []
    unmatched_dirs = list(local_dirs)
    for remote, local in zip(matched_nodes, unmatched_dirs):
      if local != remote.name:
        break
      new_matched_nodes.append(remote)
      unmatched_dirs.pop(0)
    return new_matched_nodes, unmatched_dirs

  def sync(self, user, sources, target, privacy):
    target = target if target.startswith(os.sep) else os.sep + target
    sources = list(itertools.chain(*[glob.glob(source) for source in sources]))
    print 'Syncing local folders "%s" to SmugMug folder "%s".' % (
      ', '.join(sources), target)

    user = user or self._smugmug.get_auth_user()
    matched, unmatched_dirs = self.path_to_node(user, target)
    if unmatched_dirs:
      print 'Target folder not found: "%s".' % target
      return

    for source in sources:
      for subdir, dirs, files in os.walk(source):
        media_files = [f for f in files if self._is_media(f)]
        if media_files:
          local_dirs = os.path.join(target, subdir).split(os.sep)
          if dirs:
            local_dirs.append('Images from folder ' + local_dirs[-1])

          matched, unmatched = self._get_common_path(matched, local_dirs)
          matched, unmatched = self._match_nodes(matched, unmatched)
          if unmatched:
            matched = self._create_children(
              matched, unmatched, 'Album', privacy)
          else:
            print 'Found matching remote album "%s".' % os.path.join(
              *local_dirs)

          for f in media_files:
            self._sync_file(os.path.join(subdir, f), matched[-1])

  def _sync_file(self, file_path, node):
    file_name = file_path.split(os.sep)[-1].strip()
    file_content = open(file_path, 'rb').read()
    remote_matches = node.child_nodes_by_name.get(file_name, [])
    if len(remote_matches) > 1:
      print 'Skipping %s, multiple remote nodes matches local file.' % file_path
      return

    if remote_matches:
      remote_file = remote_matches[0]
      if remote_file['Format'].lower() in VIDEO_EXT:
        # Video files are modified by SmugMug server side, so we cannot use the
        # MD5 to check if the file needs a re-sync. Use the last modification
        # time instead.
        remote_time = datetime.strptime(
          remote_file.get('ImageMetadata')['DateTimeModified'],
          '%Y-%m-%dT%H:%M:%S')

        try:
          parser = guessParser(StringInputStream(file_content))
          metadata = extractMetadata(parser)
          file_time = max(metadata.getValues('last_modification') +
                          metadata.getValues('creation_date'))
        except Exception as err:
          print 'Failed extracting metadata for file "%s".' % file_path
          file_time = datetime.fromtimestamp(os.path.getmtime(file_path))

        same_file = (remote_time == file_time)
      else:
        remote_md5 = remote_file['ArchivedMD5']
        file_md5 = md5.new(file_content).hexdigest()
        same_file = (remote_md5 == file_md5)

      if same_file:
        return  # File already exists on Smugmug
      else:
        print ('File "%s" exists, but has changed. '
               'Deleting old version.' % file_path)
        remote_file.delete()
        print 'Re-uploading "%s".' % file_path
    else:
      print 'Uploading "%s".' % file_path
    node.upload('Album', file_name, file_content)

  def _is_media(self, path):
    extension = os.path.splitext(path)[1][1:].lower().strip()
    return extension in self._media_ext

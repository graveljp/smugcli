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
NodeInfo = collections.namedtuple('NodeInfo', ['name', 'node'])

DEFAULT_MEDIA_EXT = ['gif', 'jpeg', 'jpg', 'mov', 'mp4', 'png']
VIDEO_EXT = ['mov', 'mp4']


class Error(Exception):
  """Base class for all exception of this module."""


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
    return self._smugmug.get('/api/v2/user/%s' % user).get('Node')

  def path_to_node(self, user, path):
    current_node = self.get_root_node(user)
    parts = filter(bool, path.split(os.sep))
    matched_nodes = [NodeInfo('', current_node)]
    unmatched_dirs = collections.deque(parts)
    for part in parts:
      current_node = current_node.get_child(part)
      if not current_node:
        break
      matched_nodes.append(NodeInfo(part, current_node))
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

    node = matched_nodes[-1].node
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
      print 'Nodes can only be created in folders.'
      print '"%s" is of type "%s".' % (parent, node['Type'])
      return None

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
      print 'Error creating node "%s".' % path
      print 'Server responded with %s.' % str(response)
      return None

    node = node.get_child(remote_name)
    if not node:
      print 'Cannot find newly created node "%s".' % path
      return None

    if node['Type'] == 'Album':
      response = node.patch('Album', json={'SortMethod': 'DateTimeOriginal'})
      if response.status_code != 200:
        print 'Failed setting SortMethod on Album "%s".' % name

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

      built_path = os.path.join(*[m.name for m in matched_nodes])
      node = matched_nodes[-1].node
      for i, part in enumerate(unmatched_dirs):
        built_path = os.path.join(built_path, part)
        params = {
          'Type': node_type if i == len(unmatched_dirs) - 1 else 'Folder',
          'Privacy': privacy,
        }
        print 'Creating %s "%s".' % (params['Type'], built_path)
        node = self.make_childnode(node, part, params)
        if not node:
          continue

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
        node = matched_nodes.pop().node
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

      name, node = matched_nodes[-1]
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

    node = matched_nodes[-1].node
    if node['Type'] != 'Album':
      print 'Cannot upload images in node of type "%s".' % node['Type']
      return

    child_nodes = self._get_child_nodes_by_name(node)

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


  def sync(self, user, sources, target):
    sources = list(itertools.chain(*[glob.glob(source) for source in sources]))
    print 'Syncing local folders %s to SmugMug folder %s.' % (
      ', '.join(sources), target)

    user = user or self._smugmug.get_auth_user()
    matched_nodes, unmatched_dirs = self.path_to_node(user, target)
    if unmatched_dirs:
      print 'Target folder not found: "%s".' % target
      return

    node = matched_nodes[-1].node
    child_nodes = self._get_child_nodes_by_name(node)

    for source in sources:
      if not os.path.isdir(source):
        print 'Source folder not found: "%s".' % source
        continue

      folder, file = os.path.split(source)
      configs = persistent_dict.PersistentDict(
        os.path.join(folder, '.smugcli'))
      if file in configs.get('ignore', []):
        print 'Skipping ignored path "%s".' % source
        continue

      self._recursive_sync(source, node, child_nodes)

  def _recursive_sync(self, current_folder, parent_node, current_nodes):
    current_name = current_folder.split(os.sep)[-1].strip()
    remote_matches = current_nodes.get(current_name, [])
    if len(remote_matches) > 1:
      print 'Skipping "%s", multiple remote nodes matches local path.' % current_folder
      return None

    folder_children = self._read_local_dir(current_folder)

    if remote_matches:
      print 'Found matching remote folder for "%s".' % current_folder
      current_node = remote_matches[0]
    else:
      current_node_type = ('Folder' if any(details.isdir for _, details
                                          in folder_children.iteritems())
                           else 'Album')

      print 'Making %s "%s".' % (current_node_type, current_folder)
      current_node = self.make_childnode(parent_node,
                                         current_folder,
                                         params={
                                           'Type': current_node_type,
                                         })

    if not current_node:
      print 'Skipping "%s", no matching remote node.' % current_folder
      return None

    child_nodes = self._get_child_nodes_by_name(current_node)

    configs = persistent_dict.PersistentDict(
      os.path.join(current_folder, '.smugcli'))
    to_ignore = set(configs.get('ignore', []))

    side_album_node = None
    for child_name, child_details in sorted(folder_children.items()):
      new_path = os.path.join(current_folder, child_name)
      if child_name in to_ignore:
        print 'Skipping ignored path "%s".' % new_path
        continue

      if current_node['Type'] == 'Folder':
        if child_details.isdir:
          self._recursive_sync(new_path, current_node, child_nodes)
        elif child_details.ismedia:
          if side_album_node == None:
            print ('Found media next to a sub-folder within "%s". '
                   'Fork a side album to store images.') % current_folder
            side_album_name = 'Images from folder ' + current_name
            side_album_path = os.path.join(current_folder, side_album_name)
            side_album_matches = child_nodes.get(side_album_name, [])
            if len(side_album_matches) > 1:
              print ('Skipping "%s", multiple remote nodes matches local '
                     'path.' % side_album_path)
              continue

            if side_album_matches:
              print 'Found matching remote folder for "%s".' % side_album_path
              side_album_node = side_album_matches[0]
            else:
              side_album_node = self.make_childnode(
                current_node, side_album_path, params={'Type': 'Album'})
            if not side_album_node:
              print 'Skipping "%s", no matching remote node.' % side_album_path
              continue

            side_album_child_nodes = self._get_child_nodes_by_name(
              side_album_node)
          self._sync_file(new_path, side_album_node, side_album_child_nodes)

      elif current_node['Type'] == 'Album':
        if child_details.isdir:
          print ('Ignoring folder "%s" found inside %s "%s". '
                 'SmugMug albums cannot have subfolders.' % (
                   child_name, current_node['Type'], current_folder))
        elif child_details.ismedia:
          self._sync_file(new_path, current_node, child_nodes)

  def _sync_file(self, file_path, album_node, album_children):
    file_name = file_path.split(os.sep)[-1].strip()
    file_content = open(file_path, 'rb').read()
    remote_matches = album_children.get(file_name, [])
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
    album_node.upload('Album', file_name, file_content)

  def _resursive_album_sync(self, current_folder, album_node, image_nodes):
    current_name = current_folder.split(os.sep)[-1].strip()
    remote_matches = current_nodes.get(current_name, [])
    if len(remote_matches) > 1:
      print 'Skipping %s, multiple remote nodes matches local path.' % current_folder
      return None

    folder_children = self._read_local_dir(current_folder)

  def _is_media(self, path):
    isfile = os.path.isfile(path)
    extension = os.path.splitext(path)[1][1:].lower().strip()
    return isfile and (extension in self._media_ext)

  def _read_local_dir(self, path):

    def get_details(child):
      full_path = os.path.join(path, child)
      isdir = os.path.isdir(full_path)
      ismedia = self._is_media(full_path)
      return Details(path=full_path,
                     isdir=isdir,
                     ismedia=ismedia)

    return {child: get_details(child) for child in os.listdir(path)}

  def _get_child_nodes_by_name(self, node):
    child_by_name = collections.defaultdict(list)
    for child in node.get_children():
      child_by_name[child.name].append(child)
    return child_by_name

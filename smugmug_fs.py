import base64
from datetime import datetime
import collections
import glob
import itertools
import json
import md5
import os
import smugmug

import persistent_dict

Details = collections.namedtuple('details', ['path', 'isdir', 'ismedia'])

DEFAULT_MEDIA_EXT = ['gif', 'jpeg', 'jpg', 'mov', 'mp4', 'png']
VIDEO_EXT = ['mov', 'mp4']

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

  def get_children(self, node, params=None):
    if 'Type' not in node:
      return

    params = params or {}
    params['start'] = 1
    params['count'] = self._smugmug.config.get('page_size', 1000)

    if node['Type'] == 'Album':
      for child in node.get('Album').get('AlbumImages', params=params) or []:
        yield child['FileName'], child
    else:
      for child in node.get('ChildNodes', params=params) or []:
        yield child['Name'], child

  def get_child(self, parent, child_name, params=None):
    for name, child in self.get_children(parent, params):
      if name == child_name:
        return child
    return None

  def path_to_node(self, user, path):
    current_node = self.get_root_node(user)
    parts = filter(bool, path.split(os.sep))
    last_node = current_node
    matched = []
    unmatched = collections.deque(parts)
    for part in parts:
      current_node = self.get_child(current_node, part)
      if not current_node:
        break
      last_node = current_node
      matched.append(part)
      unmatched.popleft()
    return last_node, matched, list(unmatched)

  def ls(self, user, path, details):
    user = user or self._smugmug.get_auth_user()
    node, matched, unmatched = self.path_to_node(user, path)
    if unmatched:
      print '"%s" not found in "%s"' % (unmatched[0], os.sep.join(matched))
      return

    nodes = [(path, node)] if 'FileName' in node else self.get_children(node)

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
    if response is None:
      print 'Cannot create child nodes under "%s"' % parent
      return None

    if response.status_code != 201:
      print 'Error creating node "%s".' % path
      print 'Server responded with %s' % str(response)
      return None

    node = self.get_child(node, remote_name)
    if not node:
      print 'Cannot find newly created node "%s"' % path
      return None

    if node['Type'] == 'Album':
      response = node.patch('Album', json={'SortMethod': 'DateTimeOriginal'})
      if response.status_code != 200:
        print 'Failed setting SortMethod on Album %s' % name

    return node

  def make_node(self, user, path, create_parents, params=None):
    user = user or self._smugmug.get_auth_user()
    node, matched, unmatched = self.path_to_node(user, path)
    if len(unmatched) > 1 and not create_parents:
      print '"%s" not found in "%s"' % (unmatched[0], os.sep.join(matched))
      return

    if not len(unmatched):
      print 'Path "%s" already exists.' % path
      return

    for part in unmatched:
      node = self.make_childnode(node, part, params)
      if not node:
        return
      matched.append(part)


  def upload(self, user, filenames, album):
    user = user or self._smugmug.get_auth_user()
    node, matched, unmatched = self.path_to_node(user, album)
    if unmatched:
      print 'Album not found: "%s"' % album
      return

    for filename in filenames:
      node.upload('Album',
                  os.path.basename(filename).strip(),
                  open(filename, 'rb').read())

  def sync(self, user, sources, target):
    sources = list(itertools.chain(*[glob.glob(source) for source in sources]))
    print 'Syncing local folders %s to SmugMug folder %s' % (
      ', '.join(sources), target)

    user = user or self._smugmug.get_auth_user()
    node, matched, unmatched = self.path_to_node(user, target)
    if unmatched:
      print 'Target folder not found: "%s"' % target
      return

    child_nodes = self._get_child_nodes_by_name(node)

    for source in sources:
      if not os.path.isdir(source):
        print 'Source folder not found: "%s"' % source
        continue

      folder, file = os.path.split(source)
      configs = persistent_dict.PersistentDict(
        os.path.join(folder, '.smugcli'))
      if file in configs.get('ignore', []):
        print 'Skipping ignored path %s' % source
        continue

      self._recursive_sync(source, node, child_nodes)

  def _recursive_sync(self, current_folder, parent_node, current_nodes):
    current_name = current_folder.split(os.sep)[-1].strip()
    remote_matches = current_nodes.get(current_name, [])
    if len(remote_matches) > 1:
      print 'Skipping %s, multiple remote nodes matches local path.' % current_folder
      return None

    folder_children = self._read_local_dir(current_folder)

    if remote_matches:
      print 'Found matching remote folder for %s' % current_folder
      current_node = remote_matches[0]
    else:
      current_node_type = ('Album' if any(details.ismedia for _, details
                                          in folder_children.iteritems())
                           else 'Folder')

      print 'Making %s %s' % (current_node_type, current_folder)
      current_node = self.make_childnode(parent_node,
                                         current_folder,
                                         params={
                                           'Type': current_node_type,
                                         })

    if not current_node:
      print 'Skipping %s, no matching remote node.' % current_folder
      return None

    child_nodes = self._get_child_nodes_by_name(current_node)

    configs = persistent_dict.PersistentDict(
      os.path.join(current_folder, '.smugcli'))
    to_ignore = set(configs.get('ignore', []))

    for child_name, child_details in sorted(folder_children.items()):
      new_path = os.path.join(current_folder, child_name)
      if child_name in to_ignore:
        print 'Skipping ignored path %s' % new_path
        continue

      if current_node['Type'] == 'Folder':
        if child_details.isdir:
          self._recursive_sync(new_path, current_node, child_nodes)
        elif child_details.ismedia:
          print 'Ignoring %s, can\'t be copied to a folder' % new_path
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
        remote_time = remote_file.get('ImageMetadata')['DateTimeModified']
        file_time = datetime.utcfromtimestamp(
          os.path.getmtime(file_path)).strftime('%Y-%m-%dT%H:%M:%S')
        same_file = (remote_time == file_time)
      else:
        remote_md5 = remote_file['ArchivedMD5']
        file_md5 = md5.new(file_content).hexdigest()
        same_file = (remote_md5 == file_md5)

      if same_file:
        pass  # File already exists on Smugmug
      else:

        print 'File "%s" exists, but has changed. Re-uploading.' % file_path
        remote_file.upload('Album', file_name, file_content,
                           headers={'X-Smug-ImageUri': remote_file.uri('Image')})
    else:
      print 'Uploading %s' % file_path
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
    for name, child in self.get_children(node):
      child_by_name[name].append(child)
    return child_by_name

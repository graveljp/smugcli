from . import persistent_dict
from . import task_manager  # Must be included before hachoir so stdout override works.
from . import thread_pool
from . import thread_safe_print

import six
import collections
import datetime
import glob
if six.PY2:
  from hachoir_metadata import extractMetadata
  from hachoir_parser import guessParser
  from hachoir_core.stream import StringInputStream
  from hachoir_core import config as hachoir_config
else:
  from hachoir.metadata import extractMetadata
  from hachoir.parser import guessParser
  from hachoir.stream import StringInputStream
  from hachoir.core import config as hachoir_config

from six.moves import input
import itertools
import json
import hashlib
import os
import requests
from six.moves import urllib

hachoir_config.quiet = True

DEFAULT_MEDIA_EXT = ['gif', 'jpeg', 'jpg', 'mov', 'mp4', 'png']
VIDEO_EXT = ['mov', 'mp4']


class Error(Exception):
  """Base class for all exception of this module."""


class RemoteDataError(Error):
  """Error raised when the remote structure is incompatible with SmugCLI."""


class SmugMugLimitsError(Error):
  """Error raised when SmugMug limits are reached (folder depth, size. etc.)"""


class UnexpectedResponseError(Error):
  """Error raised when encountering unexpected data returned by SmugMug."""


class SmugMugFS(object):
  def __init__(self, smugmug):
    self._smugmug = smugmug
    self._aborting = False

    # Pre-compute some common variables.
    self._media_ext = [
      ext.lower() for ext in
      self.smugmug.config.get('media_extensions', DEFAULT_MEDIA_EXT)]

  @property
  def smugmug(self):
    return self._smugmug

  def abort(self):
    self._aborting = True

  def get_root_node(self, user):
    return self._smugmug.get_root_node(user)

  def path_to_node(self, user, path):
    current_node = self.get_root_node(user)
    parts = list(filter(bool, path.split(os.sep)))
    nodes = [current_node]
    return self._match_nodes(nodes, parts)

  def _match_nodes(self, matched_nodes, dirs):
    unmatched_dirs = collections.deque(dirs)
    for dir in dirs:
      child_node = matched_nodes[-1].get_child(dir)
      if not child_node:
        break

      matched_nodes.append(child_node)
      unmatched_dirs.popleft()
    return matched_nodes, list(unmatched_dirs)

  def _match_or_create_nodes(self, matched_nodes, dirs, node_type, privacy):
    folder_depth = len(matched_nodes) + len(dirs)
    folder_depth -= 1 if node_type == 'Album' else 0
    if folder_depth >= 7:  # matched_nodes include an extra node for the root.
      raise SmugMugLimitsError(
        'Cannot create "%s", SmugMug does not support folder more than 5 level '
        'deep.' % os.sep.join([matched_nodes[-1].path] + dirs))

    all_nodes = list(matched_nodes)
    for i, dir in enumerate(dirs):
      params = {
        'Type': node_type if i == len(dirs) - 1 else 'Folder',
        'Privacy': privacy,
      }
      all_nodes.append(all_nodes[-1].get_or_create_child(dir, params))
    return all_nodes

  def get(self, url):
    scheme, netloc, path, query, fragment = urllib.parse.urlsplit(url)
    params = urllib.parse.parse_qs(query)
    result = self._smugmug.get_json(path, params=params)
    print(json.dumps(result, sort_keys=True, indent=2, separators=(',', ': ')))

  def ignore_or_include(paths, ignore):
    files_by_folder = collections.defaultdict(list)
    for folder, file in [os.path.split(path) for path in paths]:
      files_by_folder[folder].append(file)

    for folder, files in six.iteritems(files_by_folder):
      if not os.path.isdir(folder or '.'):
        print('Can\'t find folder "%s".' % folder)
        return
      for file in files:
        full_path = os.path.join(folder, file)
        if not os.path.exists(full_path):
          print('"%s" doesn\'t exists.' % full_path)
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
      print('"%s" not found in "%s".' % (
        unmatched_dirs[0], os.sep.join(m.name for m in matched_nodes)))
      return

    node = matched_nodes[-1]
    nodes = ([(path, node)] if 'FileName' in node else
             [(child.name, child) for child in node.get_children()])

    for name, node in nodes:
      if details:
        print(json.dumps(node.json, sort_keys=True, indent=2,
                         separators=(',', ': ')))
      else:
        print(name)

  def make_node(self, user, paths, create_parents, node_type, privacy):
    user = user or self._smugmug.get_auth_user()
    for path in paths:
      matched_nodes, unmatched_dirs = self.path_to_node(user, path)
      if len(unmatched_dirs) > 1 and not create_parents:
        print('"%s" not found in "%s".' % (
          unmatched_dirs[0], os.sep.join(m.name for m in matched_nodes)))
        continue

      if not len(unmatched_dirs):
        print('Path "%s" already exists.' % path)
        continue

      self._match_or_create_nodes(
        matched_nodes, unmatched_dirs, node_type, privacy)

  def rmdir(self, user, parents, dirs):
    user = user or self._smugmug.get_auth_user()
    for dir in dirs:
      matched_nodes, unmatched_dirs = self.path_to_node(user, dir)
      if unmatched_dirs:
        print('Folder or album "%s" not found.' % dir)
        continue

      matched_nodes.pop(0)
      while matched_nodes:
        current_dir = os.sep.join(m.name for m in matched_nodes)
        node = matched_nodes.pop()
        if len(node.get_children({'count': 1})):
          print('Cannot delete %s: "%s" is not empty.' % (
            node['Type'], current_dir))
          break

        print('Deleting "%s".' % current_dir)
        node.delete()

        if not parents:
          break

  def _ask(self, question):
    answer = input(question)
    return answer.lower() in ['y', 'yes']

  def rm(self, user, force, recursive, paths):
    user = user or self._smugmug.get_auth_user()
    for path in paths:
      matched_nodes, unmatched_dirs = self.path_to_node(user, path)
      if unmatched_dirs:
        print('"%s" not found.' % path)
        continue

      node = matched_nodes[-1]
      if recursive or len(node.get_children({'count': 1})) == 0:
        if force or self._ask('Remove %s node "%s"? ' % (node['Type'], path)):
          print('Removing "%s".' % path)
          node.delete()
      else:
        print('Folder "%s" is not empty.' % path)

  def upload(self, user, filenames, album):
    user = user or self._smugmug.get_auth_user()
    matched_nodes, unmatched_dirs = self.path_to_node(user, album)
    if unmatched_dirs:
      print('Album not found: "%s".' % album)
      return

    node = matched_nodes[-1]
    if node['Type'] != 'Album':
      print('Cannot upload images in node of type "%s".' % node['Type'])
      return

    for filename in itertools.chain(*(glob.glob(f) for f in filenames)):
      file_basename = os.path.basename(filename).strip()
      if node.get_child(file_basename):
        print('Skipping "%s", file already exists in Album "%s".' % (filename,
                                                                     album))
        continue

      print('Uploading "%s" to "%s"...' % (filename, album))
      with open(filename, 'rb') as f:
        response = node.upload('Album',
                               file_basename,
                               f.read())
      if response.status_code != requests.codes.ok:
        print('Error uploading "%s" to "%s".' % (filename, album))
        print('Server responded with %s.' % str(response))
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

  def sync(self,
           user,
           sources,
           target,
           deprecated_target,
           force,
           privacy,
           folder_threads,
           file_threads,
           upload_threads,
           set_defaults):
    if set_defaults:
      self.smugmug.config['folder_threads'] = folder_threads
      self.smugmug.config['file_threads'] = file_threads
      self.smugmug.config['upload_threads'] = upload_threads
      print('Defaults updated.')
      return

    if deprecated_target:
      print('-t/--target argument no longer exists.')
      print('Specify the target folder as the last positinal argument.')
      return

    # The argparse library doesn't seem to support having two positional
    # arguments, the first variable in length length and the second optional.
    # The first positional argument always eagerly grabs all values specified.
    # We therefore need to distribute that last value to the second argument
    # when it's specified.
    if len(sources) >= 2 and target == [os.sep]:
      target = sources.pop()
    else:
      target = target[0]

    # Approximate worse case: each folder and file threads work on a different
    # folders, and all folders are 5 level deep.
    self._smugmug.garbage_collector.set_max_children_cache(
      folder_threads + file_threads + 5)

    # Make sure that the source paths exist.
    globbed = [(source, glob.glob(source)) for source in sources]
    not_found = [g[0] for g in globbed if not g[1]]
    if not_found:
      print('File%s not found:\n  %s' % (
        's' if len(not_found) > 1 else '', '\n  '.join(not_found)))
      return
    all_sources = list(itertools.chain.from_iterable([g[1] for g in globbed]))

    file_sources = [s for s in all_sources if os.path.isfile(s)]
    dir_sources = [s for s in all_sources if os.path.isdir(s)]

    files_by_path = collections.defaultdict(list)
    for file_source in file_sources:
      path, filename = os.path.split(file_source)
      files_by_path[path or '.'].append(filename)

    # Make sure that the destination node exists.
    user = user or self._smugmug.get_auth_user()
    target = target if target.startswith(os.sep) else os.sep + target
    matched, unmatched_dirs = self.path_to_node(user, target)
    if unmatched_dirs:
      print('Target folder not found: "%s".' % target)
      return
    target_type = matched[-1]['Type'].lower()

    # Abort if invalid operations are requested.
    if target_type == 'folder' and file_sources:
      print('Can\'t upload files to folder. Please sync to an album node.')
      return
    elif (target_type == 'album' and
          any(not d.endswith(os.sep) for d in dir_sources)):
      print('Can\'t upload folders to an album. Please sync to a folder node.')
      return

    # Request confirmation before proceeding.
    if len(all_sources) == 1:
      print('Syncing "%s" to SmugMug %s "%s".' % (
        all_sources[0], target_type, target))
    else:
      print('Syncing:\n%s\nto SmugMug %s "%s".' % (
        '  ' + '\n  '.join(all_sources), target_type, target))
    if not force and not self._ask('Proceed (yes/no)? '):
      return

    with task_manager.TaskManager() as manager, \
         thread_safe_print.ThreadSafePrint(), \
         thread_pool.ThreadPool(upload_threads) as upload_pool, \
         thread_pool.ThreadPool(file_threads) as file_pool, \
         thread_pool.ThreadPool(folder_threads) as folder_pool:
      for source, walk_steps in sorted(
          [(d, os.walk(d)) for d in dir_sources] +
          [(p + os.sep, [(p, [], f)])
           for p, f in files_by_path.items()]):
        for walk_step in walk_steps:
          if self._aborting:
            return
          folder_pool.add(self._sync_folder,
                          manager,
                          file_pool,
                          upload_pool,
                          source,
                          target,
                          privacy,
                          walk_step,
                          matched,
                          unmatched_dirs)
    print('Sync complete.')

  def _sync_folder(self,
                   manager,
                   file_pool,
                   upload_pool,
                   source,
                   target,
                   privacy,
                   walk_step,
                   matched,
                   unmatched_dirs):
    if self._aborting:
      return
    subdir, dirs, files = walk_step
    media_files = [f for f in files if self._is_media(f)]
    if media_files:
      rel_subdir = os.path.relpath(subdir, os.path.split(source)[0])
      target_dirs = os.path.normpath(
        os.path.join(target, rel_subdir)).split(os.sep)
      target_dirs = [d.strip() for d in target_dirs]

      if dirs:
        target_dirs.append('Images from folder ' + target_dirs[-1])

      matched, unmatched = self._get_common_path(matched, target_dirs)
      matched, unmatched = self._match_nodes(matched, unmatched)

      if unmatched:
        matched = self._match_or_create_nodes(
          matched, unmatched, 'Album', privacy)
      else:
        print('Found matching remote album "%s".' % os.path.join(*target_dirs))

      for f in media_files:
        if self._aborting:
          return
        file_pool.add(self._sync_file,
                      manager,
                      os.path.join(subdir, f),
                      matched[-1],
                      upload_pool)

  def _sync_file(self, manager, file_path, node, upload_pool):
    if self._aborting:
      return
    with manager.start_task(1, '* Syncing file "%s"...' % file_path):
      file_name = file_path.split(os.sep)[-1].strip()
      with open(file_path, 'rb') as f:
        file_content = f.read()
      remote_file = node.get_child(file_name)

      if remote_file:
        if remote_file['Format'].lower() in VIDEO_EXT:
          # Video files are modified by SmugMug server side, so we cannot use
          # the MD5 to check if the file needs a re-sync. Use the last
          # modification time instead.
          remote_time = datetime.datetime.strptime(
            remote_file.get('ImageMetadata')['DateTimeModified'],
            '%Y-%m-%dT%H:%M:%S')

          try:
            parser = guessParser(StringInputStream(file_content))
            metadata = extractMetadata(parser)
            file_time = max(metadata.getValues('last_modification') +
                            metadata.getValues('creation_date'))
          except Exception as err:
            print('Failed extracting metadata for file "%s".' % file_path)
            file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

          time_delta = abs(remote_time - file_time)
          same_file = (time_delta <= datetime.timedelta(seconds=1))
        else:
          remote_md5 = remote_file['ArchivedMD5']
          file_md5 = hashlib.md5(file_content).hexdigest()
          same_file = (remote_md5 == file_md5)

        if same_file:
          return  # File already exists on Smugmug

      if self._aborting:
        return
      upload_pool.add(self._upload_media,
                      manager,
                      node,
                      remote_file,
                      file_path,
                      file_name,
                      file_content)

  def _upload_media(self, manager, node, remote_file, file_path, file_name, file_content):
    if self._aborting:
      return
    if remote_file:
      print('File "%s" exists, but has changed. '
            'Deleting old version.' % file_path)
      remote_file.delete()
      task = '+ Re-uploading "%s"' % file_path
    else:
      task = '+ Uploading "%s"' % file_path

    def get_progress_fn(task):
      def progress_fn(percent):
        manager.update_progress(0, task, ': %d%%' % percent)
        return self._aborting
      return progress_fn

    with manager.start_task(0, task):
      node.upload('Album', file_name, file_content,
                  progress_fn=get_progress_fn(task))

    if remote_file:
      print('Re-uploaded "%s".' % file_path)
    else:
      print('Uploaded "%s".' % file_path)

  def _is_media(self, path):
    extension = os.path.splitext(path)[1][1:].lower().strip()
    return extension in self._media_ext

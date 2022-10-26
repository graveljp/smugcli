"""File-system-like API for SmugMug."""

import contextlib
from typing import DefaultDict, List, Optional, Sequence, Tuple, Union

import collections
import datetime
import glob
import itertools
import json
import hashlib
import os
from urllib import parse

from hachoir.metadata import extractMetadata
from hachoir.parser import guessParser
from hachoir.stream import StringInputStream
from hachoir.core import config as hachoir_config

from . import persistent_dict
from . import smugmug as smugmug_lib
from . import task_manager
from . import thread_pool
from . import thread_safe_print

hachoir_config.quiet = True

DEFAULT_MEDIA_EXT = ['gif', 'jpeg', 'jpg', 'mov', 'mp4', 'png', 'heic']
VIDEO_EXT = ['mov', 'mp4']


class Error(Exception):
  """Base class for all exception of this module."""


class RemoteDataError(Error):
  """Error raised when the remote structure is incompatible with SmugCLI."""


class SmugMugLimitsError(Error):
  """Error raised when SmugMug limits are reached (folder depth, size. etc.)"""


class UnexpectedResponseError(Error):
  """Error raised when encountering unexpected data returned by SmugMug."""


class ExtractMetadataError(Error):
  """Error raised when metadata extraction fails."""


class SmugMugFS():
  """File-system-like API for SmugMug."""

  def __init__(self, smugmug: smugmug_lib.SmugMug) -> None:
    self._smugmug = smugmug
    self._aborting = False

    # Pre-compute some common variables.
    self._media_ext = [
        ext.lower() for ext in
        self.smugmug.config.get('media_extensions', DEFAULT_MEDIA_EXT)]

  @property
  def smugmug(self) -> smugmug_lib.SmugMug:
    """Returns the SmugMug web interface object."""
    return self._smugmug

  def abort(self) -> None:
    """Requests the commands that is currently running to abort."""
    self._aborting = True

  def get_root_node(self, user: str) -> smugmug_lib.Node:
    """Returns the specified user's root node."""
    return self._smugmug.get_root_node(user)

  def path_to_node(
      self, user: str, path: str
  ) -> Tuple[List[smugmug_lib.Node], List[str]]:
    """Loads the node of the specified path in the user's MugMug account."""
    current_node = self.get_root_node(user)
    parts = list(filter(bool, path.split(os.sep)))
    nodes = [current_node]
    return self._match_nodes(nodes, parts)

  def _match_nodes(
      self, matched_nodes: List[smugmug_lib.Node], dirs: Sequence[str]
  ) -> Tuple[List[smugmug_lib.Node], List[str]]:
    unmatched_dirs = collections.deque(dirs)
    for child in dirs:
      child_node = matched_nodes[-1].get_child(child)
      if not child_node:
        break

      matched_nodes.append(child_node)
      unmatched_dirs.popleft()
    return matched_nodes, list(unmatched_dirs)

  def _match_or_create_nodes(
      self,
      matched_nodes: List[smugmug_lib.Node],
      dirs: List[str],
      node_type: str,
      privacy: str
  ) -> List[smugmug_lib.Node]:
    folder_depth = len(matched_nodes) + len(dirs)
    folder_depth -= 1 if node_type == 'Album' else 0
    if folder_depth >= 7:  # matched_nodes include an extra node for the root.
      raise SmugMugLimitsError(
          f'Cannot create "{os.sep.join([matched_nodes[-1].path] + dirs)}", '
          'SmugMug does not support folder more than 5 level deep.')

    all_nodes = list(matched_nodes)
    for i, child in enumerate(dirs):
      params = {
          'Type': node_type if i == len(dirs) - 1 else 'Folder',
          'Privacy': privacy,
      }
      all_nodes.append(all_nodes[-1].get_or_create_child(child, params))
    return all_nodes

  def get(self, url: str) -> None:
    """Load the specified SmugMug API URL and return its JSON content."""
    scheme, netloc, path, query, fragment = parse.urlsplit(url)
    del scheme, netloc, fragment  # Unused.
    params = parse.parse_qs(query)
    result = self._smugmug.get_json(path, params=params)
    print(json.dumps(result, sort_keys=True, indent=2, separators=(',', ': ')))

  def ignore_or_include(self, paths: Sequence[str], ignore: bool) -> None:
    """Set a path to be ignored or included in the sync operation."""
    files_by_folder = collections.defaultdict(list)
    for folder, file in [os.path.split(path) for path in paths]:
      files_by_folder[folder].append(file)

    for folder, files in files_by_folder.items():
      if not os.path.isdir(folder or '.'):
        print(f'Can\'t find folder "{folder}".')
        return
      for file in files:
        full_path = os.path.join(folder, file)
        if not os.path.exists(full_path):
          print(f'"{full_path}" doesn\'t exists.')
          return

      configs = persistent_dict.PersistentDict(os.path.join(folder, '.smugcli'))
      original_ignore = configs.get('ignore', [])
      if ignore:
        updated_ignore = list(set(original_ignore) | set(files))
      else:
        updated_ignore = list(set(original_ignore) ^ (set(files) &
                                                      set(original_ignore)))
      configs['ignore'] = updated_ignore

  def ls(  # pylint: disable=invalid-name
      self, user: Optional[str], path: str, details: bool
  ) -> None:
    """Lists the content of a SmugMug folder."""
    user = user or self._smugmug.get_auth_user()
    matched_nodes, unmatched_dirs = self.path_to_node(user, path)
    if unmatched_dirs:
      print(f'"{unmatched_dirs[0]}" not found '
            f'in "{os.sep.join(m.name for m in matched_nodes)}".')
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

  def make_node(
      self,
      user: Optional[str],
      paths: Sequence[str],
      create_parents: bool,
      node_type: str,
      privacy: str
  ) -> None:
    """Create a node in the SmugMug database."""
    user = user or self._smugmug.get_auth_user()
    for path in paths:
      matched_nodes, unmatched_dirs = self.path_to_node(user, path)
      if len(unmatched_dirs) > 1 and not create_parents:
        print(f'"{unmatched_dirs[0]}" not found '
              f'in "{os.sep.join(m.name for m in matched_nodes)}".')
        continue

      if len(unmatched_dirs) == 0:
        print(f'Path "{path}" already exists.')
        continue

      self._match_or_create_nodes(
          matched_nodes, unmatched_dirs, node_type, privacy)

  def rmdir(  # pylint: disable=invalid-name
      self,
      user: Optional[str],
      parents: bool,
      dirs: Sequence[str]
  ) -> None:
    """Deletes a folder in SmugMug."""
    user = user or self._smugmug.get_auth_user()
    for name in dirs:
      matched_nodes, unmatched_dirs = self.path_to_node(user, name)
      if unmatched_dirs:
        print(f'Folder or album "{name}" not found.')
        continue

      matched_nodes.pop(0)
      while matched_nodes:
        current_dir = os.sep.join(m.name for m in matched_nodes)
        node = matched_nodes.pop()
        if len(node.get_children({'count': 1})):
          node_type = node['Type']
          print(f'Cannot delete {node_type}: "{current_dir}" is not empty.')
          break

        print(f'Deleting "{current_dir}".')
        node.delete()

        if not parents:
          break

  def _ask(self, question: str) -> bool:
    answer = input(question)
    return answer.lower() in ['y', 'yes']

  def rm(  # pylint: disable=invalid-name
      self,
      user: Optional[str],
      force: bool,
      recursive: bool,
      paths: Sequence[str]
  ) -> None:
    """Deletes a file in SmugMug."""
    user = user or self._smugmug.get_auth_user()
    for path in paths:
      matched_nodes, unmatched_dirs = self.path_to_node(user, path)
      if unmatched_dirs:
        print(f'"{path}" not found.')
        continue

      node = matched_nodes[-1]
      if recursive or len(node.get_children({'count': 1})) == 0:
        node_type = node['Type']
        if force or self._ask(f'Remove {node_type} node "{path}"? '):
          print(f'Removing "{path}".')
          node.delete()
      else:
        print(f'Folder "{path}" is not empty.')

  def upload(self,
             user: Optional[str],
             filenames: Sequence[str],
             album: str) -> None:
    """Upload a file to SmugMug."""
    user = user or self._smugmug.get_auth_user()
    matched_nodes, unmatched_dirs = self.path_to_node(user, album)
    if unmatched_dirs:
      print(f'Album not found: "{album}".')
      return

    node = matched_nodes[-1]
    node_type = node['Type']
    if node_type != 'Album':
      print(f'Cannot upload images in node of type "{node_type}".')
      return

    for filename in itertools.chain(*(glob.glob(f) for f in filenames)):
      file_basename = os.path.basename(filename).strip()
      if node.get_child(file_basename):
        print(f'Skipping "{filename}", file already exists in Album "{album}".')
        continue

      print(f'Uploading "{filename}" to "{album}"...')
      with open(filename, 'rb') as file:
        node.upload('Album', file_basename, file.read())

  def _get_common_path(
      self,
      matched_nodes: Sequence[smugmug_lib.Node],
      local_dirs: Sequence[str]
  ) -> Tuple[List[smugmug_lib.Node], List[str]]:
    new_matched_nodes = []
    unmatched_dirs = list(local_dirs)
    for remote, local in zip(matched_nodes, unmatched_dirs):
      if local != remote.name:
        break
      new_matched_nodes.append(remote)
      unmatched_dirs.pop(0)
    return new_matched_nodes, unmatched_dirs

  def sync(self,
           user: Optional[str],
           sources: List[str],
           target: str,
           deprecated_target: str,
           force: bool,
           privacy: str,
           folder_threads: int,
           file_threads: int,
           upload_threads: int,
           set_defaults: bool) -> None:
    """Synchronize a local folder with a folder in SmugMug"""
    if set_defaults:
      self.smugmug.config['folder_threads'] = folder_threads
      self.smugmug.config['file_threads'] = file_threads
      self.smugmug.config['upload_threads'] = upload_threads
      print('Defaults updated.')
      return

    if deprecated_target:
      print('-t/--target argument no longer exists.')
      print('Specify the target folder as the last positional argument.')
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
    globed = [(source, glob.glob(source)) for source in sources]
    not_found = [g[0] for g in globed if not g[1]]
    if not_found:
      print('File%s not found:\n  %s' % (
          's' if len(not_found) > 1 else '', '\n  '.join(not_found)))
      return
    all_sources = list(itertools.chain.from_iterable([g[1] for g in globed]))

    file_sources = [s for s in all_sources if os.path.isfile(s)]
    dir_sources = [s for s in all_sources if os.path.isdir(s)]

    files_by_path = collections.defaultdict(
        list)  # type: DefaultDict[str, List[str]]
    for file_source in file_sources:
      path, filename = os.path.split(file_source)
      files_by_path[path or '.'].append(filename)

    # Make sure that the destination node exists.
    user = user or self._smugmug.get_auth_user()
    target = target if target.startswith(os.sep) else os.sep + target
    matched, unmatched_dirs = self.path_to_node(user, target)
    if unmatched_dirs:
      print(f'Target folder not found: "{target}".')
      return
    target_type = matched[-1]['Type'].lower()

    # Abort if invalid operations are requested.
    if target_type == 'folder' and file_sources:
      print('Can\'t upload files to folder. Please sync to an album node.')
      return
    if (target_type == 'album' and
        any(not d.endswith(os.sep) for d in dir_sources)):
      print('Can\'t upload folders to an album. Please sync to a folder node.')
      return

    # Request confirmation before proceeding.
    if len(all_sources) == 1:
      print(f'Syncing "{all_sources[0]}" to SmugMug {target_type} "{target}".')
    else:
      print('Syncing:\n'
            '  ' + '\n  '.join(all_sources) + '\n'
            f'to SmugMug {target_type} "{target}".')
    if not force and not self._ask('Proceed (yes/no)? '):
      return

    with contextlib.ExitStack() as stack:
      manager = stack.enter_context(task_manager.TaskManager())
      stack.enter_context(thread_safe_print.ThreadSafePrint())
      upload_pool = stack.enter_context(thread_pool.ThreadPool(upload_threads))
      file_pool = stack.enter_context(thread_pool.ThreadPool(file_threads))
      folder_pool = stack.enter_context(thread_pool.ThreadPool(folder_threads))

      empty_list = []  # type: List[str]
      for source, walk_steps in sorted(
          [(d, os.walk(d)) for d in dir_sources] +
          [(p + os.sep, [(p, empty_list, f)])
           for p, f in files_by_path.items()]):
        # Filter-out files and folders that must be ignored.
        steps = []  # type: List[Tuple[str, List[str], List[str]]]
        for walk_step in walk_steps:
          if self._aborting:
            return
          subdir, dirs, files = walk_step
          configs = persistent_dict.PersistentDict(os.path.join(subdir,
                                                                '.smugcli'))
          ignored = set(configs.get('ignore', []))
          dirs[:] = set(dirs) - ignored  # Prune dirs from os.walk traversal.
          files[:] = set(files) - ignored
          steps.append((subdir, dirs, files))

        # Process files in sorted order to make unit tests deterministic. We
        # can't merge this loop with the previous one because calling `sorted`
        # directly on the result of os.walk in `walk_step` would prevent us from
        # pruning directories from the walk (os.walk returns a generator which
        # can't be iterated on multiple times).
        for walk_step in sorted(steps):
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
                          matched)
    print('Sync complete.')

  def _sync_folder(self,
                   manager: task_manager.TaskManager,
                   file_pool: thread_pool.ThreadPool,
                   upload_pool: thread_pool.ThreadPool,
                   source: str,
                   target: str,
                   privacy: str,
                   walk_step: Tuple[str, List[str], List[str]],
                   matched: Sequence[smugmug_lib.Node]) -> None:
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
        print(f'Found matching remote album "{os.path.join(*target_dirs)}".')

      # Iterate in sorted order to make unit tests deterministic.
      for file in sorted(media_files):
        if self._aborting:
          return
        file_pool.add(self._sync_file,
                      manager,
                      os.path.join(subdir, file),
                      matched[-1],
                      upload_pool)

  def _sync_file(self,
                 manager: task_manager.TaskManager,
                 file_path: str,
                 node: smugmug_lib.Node,
                 upload_pool: thread_pool.ThreadPool) -> None:
    if self._aborting:
      return
    with manager.start_task(category=1,
                            task=f'* Syncing file "{file_path}"...'):
      file_name = file_path.split(os.sep)[-1].strip()
      with open(file_path, 'rb') as file:
        file_content = file.read()
      file_root, file_extension = os.path.splitext(file_name)
      if file_extension.lower() == '.heic':
        # SmugMug converts HEIC files to JPEG and renames them in the process
        renamed_file = file_root + '.JPG'
        remote_file = node.get_child(renamed_file)
      else:
        remote_file = node.get_child(file_name)

      if remote_file:
        if remote_file['Format'].lower() in VIDEO_EXT:
          # Video files are modified by SmugMug server side, so we cannot use
          # the MD5 to check if the file needs a re-sync. Use the last
          # modification time instead.
          remote_time = datetime.datetime.strptime(
              remote_file.get_node('ImageMetadata')['DateTimeModified'],
              '%Y-%m-%dT%H:%M:%S')

          try:
            parser = guessParser(StringInputStream(file_content))
            metadata = extractMetadata(parser)
            if metadata is None:
              raise ExtractMetadataError(
                  f'Failed extracting metadata from video file "{file_path}".')
            file_time = max(metadata.getValues('last_modification') +
                            metadata.getValues('creation_date'))
          except Exception:  # pylint: disable=broad-except
            print(f'Failed extracting metadata for file "{file_path}".')
            file_time = datetime.datetime.fromtimestamp(
                os.path.getmtime(file_path))

          time_delta = abs(remote_time - file_time)
          same_file = (time_delta <= datetime.timedelta(seconds=1))
        elif file_extension.lower() == '.heic':
          # HEIC files are recoded to JPEG's server side by SmugMug so we cannot
          # use MD5 to check if file needs a re-sync. Moreover, no image
          # metadata (e.g. time taken timestamp) is kept in SmugMug that would
          # allow us to tell if the file is the same. Hence, for now we just
          # assume HEIC files never change and we never re-upload them.
          same_file = True
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

  def _upload_media(self,
                    manager: task_manager.TaskManager,
                    node: smugmug_lib.Node,
                    remote_file: Union[smugmug_lib.Node, None],
                    file_path: str,
                    file_name: str,
                    file_content: bytes) -> None:
    if self._aborting:
      return
    if remote_file:
      print(f'File "{file_path}" exists, but has changed. '
            'Deleting old version.')
      remote_file.delete()
      task_str = f'+ Re-uploading "{file_path}"'
    else:
      task_str = f'+ Uploading "{file_path}"'

    with manager.start_task(0, task_str) as task:
      def get_progress_fn(task: task_manager.Task):
        def progress_fn(percent: int):
          task.update_status(f': {percent:.1f}%')
          return self._aborting
        return progress_fn
      node.upload('Album', file_name, file_content,
                  progress_fn=get_progress_fn(task))

    if remote_file:
      print(f'Re-uploaded "{file_path}".')
    else:
      print(f'Uploaded "{file_path}".')

  def _is_media(self, path):
    extension = os.path.splitext(path)[1][1:].lower().strip()
    return extension in self._media_ext

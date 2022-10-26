"""Entry point for all `smugcli` commands."""

from typing import List, Optional, Tuple

import argparse
import atexit
import os
import signal
import requests

from . import persistent_dict
from . import smugmug as smugmug_lib
from . import smugmug_fs
from . import smugmug_shell
from . import version

CONFIG_FILE = os.path.expanduser('~/.smugcli')


def run(args,
        config=None,
        requests_sent: Optional[List[Tuple[
            requests.PreparedRequest, requests.Response]]] = None) -> None:
  """Run a `smugcli` command."""
  try:
    config = config or persistent_dict.PersistentDict(CONFIG_FILE)
  except persistent_dict.InvalidFileError:
    print(f'Config file ({CONFIG_FILE}) is invalid. '
          'Please fix or delete the file.')
    return

  smugmug = smugmug_lib.SmugMug(config, requests_sent)
  file_system = smugmug_fs.SmugMugFS(smugmug)

  def signal_handler(signum, frame):
    del signum, frame  # Unused
    print('Aborting...')
    file_system.abort()

  def atexit_handler():
    file_system.abort()

  atexit.register(atexit_handler)
  signal.signal(signal.SIGINT, signal_handler)
  signal.signal(signal.SIGABRT, signal_handler)
  signal.signal(signal.SIGTERM, signal_handler)

  main_parser = argparse.ArgumentParser(
      description='SmugMug command line interface.')
  subparsers = main_parser.add_subparsers(title='sub commands')

  # ---------------
  main_parser.add_argument('-V', '--version',
                           action='store_true',
                           help='Show version and exit.')

  # ---------------
  login_parser = subparsers.add_parser(
      'login',
      help='Log into the SmugMug service',
      description=('Before using smugcli, you must run this `login` command '
                   'with a valid API key. Visit '
                   'https://api.smugmug.com/api/developer/apply to generate '
                   'your own `key` and `secret`.'))
  login_parser.set_defaults(
      func=lambda a: file_system.smugmug.login(a.key, a.secret))
  login_parser.add_argument('--key',
                            type=str,
                            required=True,
                            help='SmugMug API key')
  login_parser.add_argument('--secret',
                            type=str,
                            required=True,
                            help='SmugMug API secret')
  # ---------------
  logout_parser = subparsers.add_parser(
      'logout', help='Logout of the SmugMug service')
  logout_parser.set_defaults(
      func=lambda a: file_system.smugmug.logout())

  # ---------------
  get_parser = subparsers.add_parser(
      'get', help='Do a GET request to SmugMug using the API V2 URL.')
  get_parser.set_defaults(func=lambda a: file_system.get(a.url))
  get_parser.add_argument('url',
                          type=str,
                          help=('A SmugMug V2 API URL to get the JSON response '
                                'from. Useful combined with `smugcli.py ls -l '
                                '...` which will list URI you may want to '
                                'fetch.'))
  # ---------------
  ls_parser = subparsers.add_parser(
      'ls',
      help='List the content of a folder or album.',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  ls_parser.set_defaults(
      func=lambda a: file_system.ls(a.user, a.path, a.l))
  ls_parser.add_argument('path',
                         type=str,
                         nargs='?',
                         default=os.sep,
                         help='Path to list.')
  ls_parser.add_argument('-l',
                         help=('Show the full JSON description of the node '
                               'listed. Useful with `smugcli.py get ...`, '
                               'which can be used to fetch the URIs listed in '
                               'the JSON description.'),
                         action='store_true')
  ls_parser.add_argument('-u', '--user',
                         type=str,
                         default='',
                         help=('User whose SmugMug account is to be accessed. '
                               'Uses the logged-in user by default.'))
  # ---------------
  for cmd, node_type in (('mkdir', 'Folder'), ('mkalbum', 'Album')):
    mkdir_parser = subparsers.add_parser(
        cmd,
        help=f'Create a {node_type.lower()}.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    mkdir_parser.set_defaults(func=lambda a, t=node_type: file_system.make_node(
        a.user, a.path, a.p, t, a.privacy.title()))
    mkdir_parser.add_argument('path',
                              type=str,
                              nargs='+',
                              help=f'{node_type}s to create.')
    mkdir_parser.add_argument('-p',
                              action='store_true',
                              help='Create parents if they are missing.')
    mkdir_parser.add_argument('--privacy',
                              type=str,
                              default='public',
                              choices=[
                                  'public', 'private', 'unlisted'],
                              help='Access control for the created folders.')
    mkdir_parser.add_argument('-u', '--user',
                              type=str,
                              default='',
                              help=('User whose SmugMug account is to be '
                                    'accessed. Uses the logged-in user by '
                                    'default.'))
  # ---------------
  rmdir_parser = subparsers.add_parser(
      'rmdir', help='Remove a folder(s) if they are empty.')
  rmdir_parser.set_defaults(
      func=lambda a: file_system.rmdir(a.user, a.parents, a.dirs))
  rmdir_parser.add_argument('-p', '--parents',
                            action='store_true',
                            help=('Remove parent directory as well if they are '
                                  'empty'))
  rmdir_parser.add_argument('-u', '--user',
                            type=str,
                            default='',
                            help=('User whose SmugMug account is to be '
                                  'accessed. Uses the logged-in user by '
                                  'default.'))
  rmdir_parser.add_argument('dirs',
                            type=str,
                            nargs='+', help='Directories to create.')
  # ---------------
  rm_parser = subparsers.add_parser(
      'rm', help='Remove files from SmugMug.')
  rm_parser.set_defaults(
      func=lambda a: file_system.rm(a.user, a.force, a.recursive, a.paths))
  rm_parser.add_argument('-u', '--user',
                         type=str,
                         default='',
                         help=('User whose SmugMug account is to be accessed. '
                               'Uses the logged-in user by default.'))
  rm_parser.add_argument('-f', '--force',
                         action='store_true',
                         help=('Do not prompt before deleting files.'))
  rm_parser.add_argument('-r', '--recursive',
                         action='store_true',
                         help=('Recursively delete all of folder\'s content.'))
  rm_parser.add_argument('paths',
                         type=str,
                         nargs='+', help='Path to remove.')
  # ---------------
  upload_parser = subparsers.add_parser(
      'upload', help='Upload files to SmugMug.')
  upload_parser.set_defaults(
      func=lambda a: file_system.upload(a.user, a.src, a.album))
  upload_parser.add_argument('src',
                             type=str,
                             nargs='+', help='Files to upload.')
  upload_parser.add_argument('album',
                             type=str,
                             help='Path to the album.')
  upload_parser.add_argument('-u', '--user',
                             type=str,
                             default='',
                             help=('User whose SmugMug account is to be '
                                   'accessed. Uses the logged-in user by '
                                   'default.'))
  # ---------------
  sync_parser = subparsers.add_parser(
      'sync',
      help='Synchronize all local albums with SmugMug.',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  sync_parser.set_defaults(
      func=lambda a: file_system.sync(a.user,
                                      a.source,
                                      a.target,
                                      a.deprecated_target,
                                      a.force,
                                      a.privacy.title(),
                                      a.folder_threads,
                                      a.file_threads,
                                      a.upload_threads,
                                      a.set_defaults))
  sync_parser.add_argument('source',
                           type=str,
                           nargs='*',
                           default=['.'],
                           help=('Folders/files to recursively sync to the '
                                 'target SmugMug location. For paths ending '
                                 f'with "{os.sep}", the content of the folder '
                                 'is synced instead of the folder itself.'))
  sync_parser.add_argument('target',
                           type=str,
                           nargs='?',
                           default=[os.sep],
                           help=('The destination folder in which to upload '
                                 'data.'))
  sync_parser.add_argument('-t', '--target',
                           type=str,
                           dest='deprecated_target',
                           metavar='TARGET',
                           help=('DEPRECATED. -t/--target is no longer needed, '
                                 'specify the target folder as the last '
                                 'positional argument.'))
  sync_parser.add_argument('-f', '--force',
                           action='store_true',
                           help=('Do not ask for confirmation before staring '
                                 'sync operation.'))
  sync_parser.add_argument('--privacy',
                           type=str,
                           default='public',
                           choices=['public', 'private', 'unlisted'],
                           help='Access control for the created folders.')
  sync_parser.add_argument('-u', '--user',
                           type=str,
                           default='',
                           help=('User whose SmugMug account is to be '
                                 'accessed. Uses the logged-in user by '
                                 'default.'))
  sync_parser.add_argument('-Ft', '--folder_threads',
                           type=int,
                           default=config.get('folder_threads', 4),
                           metavar='N',
                           help='Number of folders scanned in parallel.')
  sync_parser.add_argument('-ft', '--file_threads',
                           type=int,
                           default=config.get('file_threads', 16),
                           metavar='N',
                           help=('Number of files scanned in parallel. Files '
                                 'read from disk and compared to the content '
                                 'the SmugMug servers.'))
  sync_parser.add_argument('-ut', '--upload_threads',
                           type=int,
                           default=config.get('upload_threads', 3),
                           metavar='N',
                           help='Number of file upload happening in parallel.')
  sync_parser.add_argument('--set_defaults',
                           action='store_true',
                           help=('Save the current settings (thread count) as '
                                 'defaults to be used next time.'))

  # ---------------
  ignore_parser = subparsers.add_parser(
      'ignore', help='Mark paths to be ignored during sync.')
  ignore_parser.set_defaults(
      func=lambda a: file_system.ignore_or_include(a.paths, True))
  ignore_parser.add_argument('paths',
                             type=str,
                             nargs='+',
                             help=('List of paths to ignore during sync.'))
  # ---------------
  include_parser = subparsers.add_parser(
      'include',
      help='Mark paths to be included during sync.',
      description=('Mark paths to be included during sync. Everything is '
                   'included by default, this commands is used to negate the '
                   'effect of the "ignore" command.'))
  include_parser.set_defaults(
      func=lambda a: file_system.ignore_or_include(a.paths, False))
  include_parser.add_argument('paths',
                              type=str,
                              nargs='+',
                              help=('List of paths to include during sync.'))
  # ---------------
  smugmug_shell.SmugMugShell.set_parser(main_parser)
  shell_parser = subparsers.add_parser(
      'shell', help=('Start smugcli in interactive shell mode.'))
  shell_parser.set_defaults(
      func=lambda a: smugmug_shell.SmugMugShell(file_system).cmdloop())
  # ---------------

  parsed = main_parser.parse_args(args)

  if parsed.version:
    print('Version: ' + version.__version__)
    return

  if not hasattr(parsed, 'func'):
    main_parser.print_help()
    return

  try:
    parsed.func(parsed)
  except smugmug_fs.Error as exc:
    print(exc)
  except smugmug_lib.NotLoggedInError:
    return

#!/usr/bin/python
# Command line tool for SmugMug. Uses SmugMug API V2.

from . import persistent_dict
from . import smugmug as smugmug_lib
from . import smugmug_fs
from . import smugmug_shell

import argparse
import atexit
import collections
import inspect
import json
import os
import signal
import six
import sys


CONFIG_FILE = os.path.expanduser('~/.smugcli')

if six.PY3:
  def arg_str_type(string):
    return string
else:
  def arg_str_type(string):
    return six.text_type(string, 'utf8')


def run(args, config=None, requests_sent=None):
  try:
    config = config or persistent_dict.PersistentDict(CONFIG_FILE)
  except persistent_dict.InvalidFileError:
    print('Config file (%s) is invalid. '
          'Please fix or delete the file.' % CONFIG_FILE)
    return

  smugmug = smugmug_lib.SmugMug(config, requests_sent)
  fs = smugmug_fs.SmugMugFS(smugmug)

  def signal_handler(signum, frame):
    print('Aborting...')
    fs.abort()
  def atexit_handler():
    fs.abort()

  atexit.register(atexit_handler)
  signal.signal(signal.SIGINT, signal_handler)
  signal.signal(signal.SIGABRT, signal_handler)
  signal.signal(signal.SIGTERM, signal_handler)

  main_parser = argparse.ArgumentParser(
    description='SmugMug commandline interface.')
  subparsers = main_parser.add_subparsers(title='sub commands')

  # ---------------
  login_parser = subparsers.add_parser(
    'login', help='Login onto the SmugMug service')
  login_parser.set_defaults(func=lambda a: fs.smugmug.login((a.key, a.secret)))
  login_parser.add_argument('--key',
                            type=arg_str_type,
                            required=True,
                            help='SmugMug API key')
  login_parser.add_argument('--secret',
                            type=arg_str_type,
                            required=True,
                            help='SmugMug API secret')
  # ---------------
  logout_parser = subparsers.add_parser(
    'logout', help='Logout of the SmugMug service')
  logout_parser.set_defaults(func=lambda a: fs.smugmug.logout())

  # ---------------
  get_parser = subparsers.add_parser(
    'get', help='Do a GET request to SmugMug using the API V2 URL.')
  get_parser.set_defaults(func=lambda a: fs.get(a.url))
  get_parser.add_argument('url',
                          type=arg_str_type,
                          help=('A SmugMug V2 API URL to get the JSON response '
                                'from. Useful combined with `smugcli.py ls -l '
                                '...` which will list URI you may want to '
                                'fetch.'))
  # ---------------
  ls_parser = subparsers.add_parser(
    'ls',
    help='List the content of a folder or album.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  ls_parser.set_defaults(func=lambda a: fs.ls(a.user, a.path, a.l))
  ls_parser.add_argument('path',
                         type=arg_str_type,
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
                         type=arg_str_type,
                         default='',
                         help=('User whose SmugMug account is to be accessed. '
                               'Uses the logged-in user by default.'))
  # ---------------
  for cmd, node_type in (('mkdir', 'Folder'), ('mkalbum', 'Album')):
    mkdir_parser = subparsers.add_parser(
      cmd,
      help='Create a %s.' % node_type.lower(),
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    mkdir_parser.set_defaults(
      func=lambda a, t=node_type: fs.make_node(a.user, a.path, a.p, t,
                                               a.privacy.title()))
    mkdir_parser.add_argument('path',
                              type=arg_str_type,
                              nargs='+',
                              help='%ss to create.' % node_type)
    mkdir_parser.add_argument('-p',
                              action='store_true',
                              help='Create parents if they are missing.')
    mkdir_parser.add_argument('--privacy',
                              type=arg_str_type,
                              default='public',
                              choices=['public', 'private', 'unlisted'],
                              help='Access control for the created folders.')
    mkdir_parser.add_argument('-u', '--user',
                              type=arg_str_type,
                              default='',
                              help=('User whose SmugMug account is to be '
                                    'accessed. Uses the logged-in user by '
                                    'default.'))
  # ---------------
  rmdir_parser = subparsers.add_parser(
    'rmdir', help='Remove a folder(s) if they are empty.')
  rmdir_parser.set_defaults(func=lambda a: fs.rmdir(a.user, a.parents, a.dirs))
  rmdir_parser.add_argument('-p', '--parents',
                            action='store_true',
                            help=('Remove parent directory as well if they are '
                                  'empty'))
  rmdir_parser.add_argument('-u', '--user',
                            type=arg_str_type,
                            default='',
                            help=('User whose SmugMug account is to be accessed. '
                                  'Uses the logged-in user by default.'))
  rmdir_parser.add_argument('dirs',
                            type=arg_str_type,
                            nargs='+', help='Directories to create.')
  # ---------------
  rm_parser = subparsers.add_parser(
    'rm', help='Remove files from SmugMug.')
  rm_parser.set_defaults(
    func=lambda a: fs.rm(a.user, a.force, a.recursive, a.paths))
  rm_parser.add_argument('-u', '--user',
                         type=arg_str_type,
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
                         type=arg_str_type,
                         nargs='+', help='Path to remove.')
  # ---------------
  upload_parser = subparsers.add_parser(
    'upload', help='Upload files to SmugMug.')
  upload_parser.set_defaults(func=lambda a: fs.upload(a.user, a.src, a.album))
  upload_parser.add_argument('src',
                             type=arg_str_type,
                             nargs='+', help='Files to upload.')
  upload_parser.add_argument('album',
                             type=arg_str_type,
                             help='Path to the album.')
  upload_parser.add_argument('-u', '--user',
                             type=arg_str_type,
                             default='',
                             help=('User whose SmugMug account is to be '
                                   'accessed. Uses the logged-in user by '
                                   'default.'))
  # ---------------
  sync_parser = subparsers.add_parser(
    'sync',
    help='Synchronize all local albums with SmugMug.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  sync_parser.set_defaults(func=lambda a: fs.sync(a.user, a.source, a.target,
                                                  a.deprecated_target,
                                                  a.force,
                                                  a.privacy.title(),
                                                  a.folder_threads,
                                                  a.file_threads,
                                                  a.upload_threads,
                                                  a.set_defaults))
  sync_parser.add_argument('source',
                           type=arg_str_type,
                           nargs='*',
                           default=['.'],
                           help=('Folders/files to recursively sync to the '
                                 'target SmugMug location. For paths ending '
                                 'with "%s", the content of the folder is '
                                 'synced instead of the folder itself.' %
                                 os.sep))
  sync_parser.add_argument('target',
                           type=arg_str_type,
                           nargs='?',
                           default=[os.sep],
                           help=('The destination folder in which to upload '
                                 'data.'))
  sync_parser.add_argument('-t', '--target',
                           type=arg_str_type,
                           dest='deprecated_target',
                           metavar='TARGET',
                           help=('DEPRECATED. -t/--targer is no longer needed, '
                                 'specify the target folder as the last '
                                 'positinal argument.'))
  sync_parser.add_argument('-f', '--force',
                           action='store_true',
                           help=('Do not ask for confirmation before staring '
                                 'sync operation.'))
  sync_parser.add_argument('--privacy',
                           type=arg_str_type,
                           default='public',
                           choices=['public', 'private', 'unlisted'],
                           help='Access control for the created folders.')
  sync_parser.add_argument('-u', '--user',
                           type=arg_str_type,
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
    func=lambda a: fs.ignore_or_include(a.paths, True))
  ignore_parser.add_argument('paths',
                             type=arg_str_type,
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
    func=lambda a: fs.ignore_or_include(a.paths, False))
  include_parser.add_argument('paths',
                              type=arg_str_type,
                              nargs='+',
                              help=('List of paths to include during sync.'))
  # ---------------
  smugmug_shell.SmugMugShell.set_parser(main_parser)
  shell_parser = subparsers.add_parser(
    'shell', help=('Start smugcli in interactive shell mode.'))
  shell_parser.set_defaults(
    func=lambda a: smugmug_shell.SmugMugShell(fs).cmdloop())
  # ---------------

  parsed = main_parser.parse_args(args)
  if not hasattr(parsed, 'func'):
    main_parser.print_help()
    return

  try:
    parsed.func(parsed)
  except smugmug_fs.Error as e:
    print(e)
  except smugmug_lib.NotLoggedInError:
    return


def main():
  run(sys.argv[1:])


if __name__ == '__main__':
  main()

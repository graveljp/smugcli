#!/usr/bin/python
# Command line tool for SmugMug. Uses SmugMug API V2.

import smugmug as smugmug_lib
import smugmug_fs
import smugmug_shell

import argparse
import collections
import inspect
import json
import persistent_dict
import os
import requests
import sys
import urlparse


CONFIG_FILE = os.path.expanduser('~/.smugcli')


class Helpers(object):
  @staticmethod
  def mknode(fs, args, node_type, parser):
    parser.add_argument('path',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='+',
                        help='%ss to create.' % node_type)
    parser.add_argument('-p',
                        action='store_true',
                        help='Create parents if they are missing.')
    parser.add_argument('--privacy',
                        type=lambda s: unicode(s, 'utf8'),
                        default='public',
                        choices=['public', 'private', 'unlisted'],
                        help='Access control for the created folders.')
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    fs.make_node(parsed.user, parsed.path, parsed.p, {
      'Type': node_type,
      'Privacy': parsed.privacy.title(),
    })

  @staticmethod
  def ignore_or_include(paths, ignore):
    files_by_folder = collections.defaultdict(list)
    for folder, file in [os.path.split(path) for path in paths]:
      files_by_folder[folder].append(file)

    for folder, files in files_by_folder.iteritems():
      if not os.path.isdir(folder or '.'):
        print 'Can\'t find folder %s' % folder
        return
      for file in files:
        full_path = os.path.join(folder, file)
        if not os.path.exists(full_path):
          print '%s doesn\'t exists' % full_path
          return

      configs = persistent_dict.PersistentDict(os.path.join(folder, '.smugcli'))
      original_ignore = configs.get('ignore', [])
      if ignore:
        updated_ignore = list(set(original_ignore) | set(files))
      else:
        updated_ignore = list(set(original_ignore) ^ (set(files) &
                                                      set(original_ignore)))
      configs['ignore'] = updated_ignore


class Commands(object):
  @staticmethod
  def login(fs, args):
    parser = argparse.ArgumentParser(
      prog='login', description='Login onto the SmugMug service')
    parser.add_argument('--key',
                        type=lambda s: unicode(s, 'utf8'),
                        required=True,
                        help='SmugMug API key')
    parser.add_argument('--secret',
                        type=lambda s: unicode(s, 'utf8'),
                        required=True,
                        help='SmugMug API secret')
    parsed = parser.parse_args(args)

    fs.smugmug.login((parsed.key, parsed.secret))

  @staticmethod
  def logout(fs, args):
    fs.smugmug.logout()

  @staticmethod
  def get(fs, args):
    url = args[0]
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
    params = urlparse.parse_qs(query)
    result = fs.smugmug.get_json(path, params=params)
    print json.dumps(result, sort_keys=True, indent=2, separators=(',', ': '))

  @staticmethod
  def ls(fs, args):
    parser = argparse.ArgumentParser(
      prog='ls', description='List the content of a folder or album.')
    parser.add_argument('path',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='?',
                        default=os.sep,
                        help='Path to list.')
    parser.add_argument('-l',
                        help='Show details.',
                        action='store_true')
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    fs.ls(parsed.user, parsed.path, parsed.l)

  @staticmethod
  def mkdir(fs, args):
    parser = argparse.ArgumentParser(
      prog='mkdir', description='Create a folder.')
    Helpers.mknode(fs, args, 'Folder', parser)

  @staticmethod
  def mkalbum(fs, args):
    parser = argparse.ArgumentParser(
      prog='mkalbum', description='Create a album.')
    Helpers.mknode(fs, args, 'Album', parser)

  @staticmethod
  def rmdir(fs, args):
    parser = argparse.ArgumentParser(
      prog='rmdir', description='Remove a folder(s) if they are empty.')
    parser.add_argument('-p', '--parents',
                        action='store_true',
                        help=('Remove parent directory as well if they are '
                              'empty'))
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-in user by default.'))
    parser.add_argument('dirs',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='+', help='Directories to create.')
    parsed = parser.parse_args(args)
    fs.rmdir(parsed.user, parsed.parents, parsed.dirs)

  @staticmethod
  def rm(fs, args):
    parser = argparse.ArgumentParser(
      prog='rmdir', description='Remove a folder(s) if they are empty.')
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-in user by default.'))
    parser.add_argument('-f', '--force',
                        action='store_true',
                        help=('Do not prompt before deleting files.'))
    parser.add_argument('-r', '--recursive',
                        action='store_true',
                        help=('Recursively delete all of folder\'s content.'))
    parser.add_argument('paths',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='+', help='Path to remove.')
    parsed = parser.parse_args(args)
    fs.rm(parsed.user, parsed.force, parsed.recursive, parsed.paths)

  @staticmethod
  def upload(fs, args):
    parser = argparse.ArgumentParser(
      prog='upload', description='Upload files to SmugMug.')
    parser.add_argument('src',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='+', help='Files to upload.')
    parser.add_argument('album',
                        type=lambda s: unicode(s, 'utf8'),
                        help='Path to the album.')
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    fs.upload(parsed.user, parsed.src, parsed.album)

  @staticmethod
  def sync(fs, args):
    parser = argparse.ArgumentParser(
      prog='sync',
      description='Synchronize all local albums with SmugMug.')
    parser.add_argument('source',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='*',
                        default=u'*',
                        help=('Folder to sync. Defaults to the local folder. '
                              'Uploads the current folder by default.'))
    parser.add_argument('-t', '--target',
                        type=lambda s: unicode(s, 'utf8'),
                        default=os.sep,
                        help=('The destination folder in which to upload data. '
                              'Uploads to the root folder by default.'))
    parser.add_argument('-u', '--user',
                        type=lambda s: unicode(s, 'utf8'),
                        default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    fs.sync(parsed.user, parsed.source, parsed.target)

  @staticmethod
  def ignore(fs, args):
    parser = argparse.ArgumentParser(
      prog='ignore',
      description='Mark paths to be ignored during sync.')
    parser.add_argument('paths',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='+',
                        help=('List of paths to ignore during sync.'))
    parsed = parser.parse_args(args)
    Helpers.ignore_or_include(parsed.paths, True)

  @staticmethod
  def include(fs, args):
    parser = argparse.ArgumentParser(
      prog='include',
      description=('Mark paths to be included during sync. '
                   'Everything is included by default, this commands is used to '
                   'negate the effect of the "ignore" command.'))
    parser.add_argument('paths',
                        type=lambda s: unicode(s, 'utf8'),
                        nargs='+',
                        help=('List of paths to include during sync.'))
    parsed = parser.parse_args(args)
    Helpers.ignore_or_include(parsed.paths, False)

  @staticmethod
  def shell(fs, args):
    shell = smugmug_shell.SmugMugShell(fs)
    shell.cmdloop()


def run(args, requests_sent=None):
  commands = {name: func for name, func in
              inspect.getmembers(Commands, predicate=inspect.isfunction)}

  smugmug_shell.SmugMugShell.set_commands(commands)

  parser = argparse.ArgumentParser(description='SmugMug commandline interface.')
  parser.add_argument('command',
                      type=lambda s: unicode(s, 'utf8'),
                      choices=commands.keys(),
                      help='The command to run.')
  parser.add_argument('args', nargs=argparse.REMAINDER)
  parsed_args = parser.parse_args(args)

  try:
    config = persistent_dict.PersistentDict(CONFIG_FILE)
  except persistent_dict.InvalidFileError:
    print ('Config file (%s) is invalid. '
           'Please fix or delete the file.' % CONFIG_FILE)
    return

  smugmug = smugmug_lib.SmugMug(config, requests_sent)
  fs = smugmug_fs.SmugMugFS(smugmug)

  try:
    commands[parsed_args.command](fs, parsed_args.args)
  except smugmug_lib.NotLoggedInError:
    return


if __name__ == '__main__':
  run(sys.argv[1:])

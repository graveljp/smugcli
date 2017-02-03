#!/usr/bin/python
# Command line tool for SmugMug. Uses SmugMug API V2.

import argparse
import inspect
import json
import persistent_dict
import os
import requests
import urlparse

import smugmug as smugmug_lib
import smugmug_shell


CONFIG_FILE = os.path.expanduser('~/.smugcli')


class Helpers(object):
  @staticmethod
  def mknode(smugmug, args, node_type, parser):
    parser.add_argument('path', type=unicode, help='%s to create.' % node_type)
    parser.add_argument('-p', action='store_true',
                        help='Create parents if they are missing.')
    parser.add_argument('--privacy', type=unicode, default='public',
                        choices=['public', 'private', 'unlisted'],
                        help='Access control for the created folders.')
    parser.add_argument('-u', '--user', type=unicode, default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    smugmug.fs.make_node(parsed.user, parsed.path, parsed.p, {
      'Type': node_type,
      'Privacy': parsed.privacy.title(),
    })

class Commands(object):
  @staticmethod
  def login(smugmug, args):
    parser = argparse.ArgumentParser(
      description='Login onto the SmugMug service')
    parser.add_argument('--key', type=unicode, required=True, help='SmugMug API key')
    parser.add_argument('--secret', type=unicode, required=True, help='SmugMug API secret')
    parsed = parser.parse_args(args)

    smugmug.login((parsed.key, parsed.secret))

  @staticmethod
  def logout(smugmug, args):
    smugmug.logout()

  @staticmethod
  def get(smugmug, args):
    url = args[0]
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
    params = urlparse.parse_qs(query)
    result = smugmug.get_json(path, params=params)
    print json.dumps(result, sort_keys=True, indent=2, separators=(',', ': '))

  @staticmethod
  def ls(smugmug, args):
    parser = argparse.ArgumentParser(
      description='List the content of a folder or album.')
    parser.add_argument('path', type=unicode, nargs='?', default=os.sep, help='Path to list.')
    parser.add_argument('-l', help='Show details.', action='store_true')
    parser.add_argument('-u', '--user', type=unicode, default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    smugmug.fs.ls(parsed.user, parsed.path, parsed.l)

  @staticmethod
  def mkdir(smugmug, args):
    parser = argparse.ArgumentParser(description='Create a folder.')
    Helpers.mknode(smugmug, args, 'Folder', parser)

  @staticmethod
  def mkalbum(smugmug, args):
    parser = argparse.ArgumentParser(description='Create a album.')
    Helpers.mknode(smugmug, args, 'Album', parser)

  @staticmethod
  def upload(smugmug, args):
    parser = argparse.ArgumentParser(description='Upload files to SmugMug.')
    parser.add_argument('src', type=unicode, nargs='+', help='Files to upload.')
    parser.add_argument('album', type=unicode, help='Path to the album.')
    parser.add_argument('-u', '--user', type=unicode, default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    smugmug.fs.upload(parsed.user, parsed.src, parsed.album)

  @staticmethod
  def sync(smugmug, args):
    parser = argparse.ArgumentParser(
      description='Synchronize all local albums with SmugMug.')
    parser.add_argument('source', type=unicode, nargs='?', default='.',
                        help=('Folder to sync. Defaults to the local folder. '
                              'Uploads the current folder by default.'))
    parser.add_argument('target', type=unicode, nargs='?', default=os.sep,
                        help=('The destination folder in which to upload data. '
                              'Uploads to the root folder by default.'))
    parser.add_argument('-u', '--user', type=unicode, default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    smugmug.fs.sync(parsed.user, parsed.source, parsed.target)

  @staticmethod
  def shell(smugmug, args):
    shell = smugmug_shell.SmugMugShell(smugmug)
    shell.cmdloop()


def main():
  commands = {name: func for name, func in
              inspect.getmembers(Commands, predicate=inspect.isfunction)}

  smugmug_shell.SmugMugShell.set_commands(commands)

  parser = argparse.ArgumentParser(description='SmugMug commandline interface.')
  parser.add_argument('command', type=unicode, choices=commands.keys(),
                 help='The command to run.')
  parser.add_argument('args', nargs=argparse.REMAINDER)
  args = parser.parse_args()

  try:
    config = persistent_dict.PersistentDict(CONFIG_FILE)
  except persistent_dict.InvalidFileError:
    print ('Config file (%s) is invalid. '
           'Please fix or delete the file.' % CONFIG_FILE)
    return

  smugmug = smugmug_lib.SmugMug(config)

  try:
    commands[args.command](smugmug, args.args)
  except smugmug_lib.NotLoggedInError:
    return


if __name__ == '__main__':
  main()

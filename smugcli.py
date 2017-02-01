#!/usr/bin/python
# Command line tool for SmugMug. Uses SmugMug API V2.

import argparse
import inspect
import json
import persistent_dict
import os
import urlparse

import smugmug as smugmug_lib
import smugmug_shell


CONFIG_FILE = os.path.expanduser('~/.smugcli')


class Commands(object):
  @staticmethod
  def login(smugmug, args):
    parser = argparse.ArgumentParser(
      description='Login onto the SmugMug service')
    parser.add_argument('--key', type=str, required=True, help='SmugMug API key')
    parser.add_argument('--secret', type=str, required=True, help='SmugMug API secret')
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
    parser.add_argument('path', type=str, nargs='?', default='/', help='Path to list.')
    parser.add_argument('-l', help='Show details.', action='store_true')
    parser.add_argument('-u', '--user', type=str, default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    user = parsed.user or smugmug.get_auth_user()
    node, matched, unmatched = smugmug.fs.path_to_node(user, parsed.path)
    if unmatched:
      print '"%s" not found in folder "%s"' % (unmatched[0], os.sep.join(matched))
      return

    if node['Type'] == 'Album':
      children = node.get('Album').get('AlbumImages') or []
      names = [child['FileName'] for child in children]
    else:
      children = node.get('ChildNodes') or []
      names = [child['Name'] for child in children]

    if parsed.l:
      print json.dumps(children.json, sort_keys=True, indent=2,
                       separators=(',', ': '))
    else:
      for name in names:
        print name

  @staticmethod
  def mkdir(smugmug, args):
    parser = argparse.ArgumentParser(
      description='List the content of a folder or album.')
    parser.add_argument('folder', type=str, help='Folder to create.')
    parser.add_argument('-p', action='store_true',
                        help='Create parents if they are missing.')
    parser.add_argument('--privacy', type=str, default='public',
                        choices=['public', 'private', 'unlisted'],
                        help='Access control for the created folders.')
    parser.add_argument('-u', '--user', type=str, default='',
                        help=('User whose SmugMug account is to be accessed. '
                              'Uses the logged-on user by default.'))
    parsed = parser.parse_args(args)

    smugmug.fs.make_node(parsed.user, parsed.folder, parsed.p, {
      'Type': 'Folder',
      'Privacy': parsed.privacy.title(),
    })

  @staticmethod
  def shell(smugmug, args):
    shell = smugmug_shell.SmugMugShell(smugmug)
    shell.cmdloop()

def main():
  commands = {name: func for name, func in
              inspect.getmembers(Commands, predicate=inspect.isfunction)}

  smugmug_shell.SmugMugShell.set_commands(commands)

  parser = argparse.ArgumentParser(description='SmugMug commandline interface.')
  parser.add_argument('command', type=str, choices=commands.keys(),
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

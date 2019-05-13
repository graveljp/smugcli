# Interactive shell for running smugcli commands

import cmd
import os
import shlex
import sys
import re

class SmugMugShell(cmd.Cmd):
  intro = 'Welcome to the SmugMug shell.   Type help or ? to list commands.\n'
  prompt = '(smugmug) '
  file = None
  _cmd_list_re = re.compile(r'.*\{([a-z,]+)\}', re.DOTALL)

  def __init__(self, fs):
    cmd.Cmd.__init__(self)
    self._fs = fs

  @classmethod
  def set_parser(cls, parser):
    usage = parser.format_usage()
    commands = SmugMugShell._cmd_list_re.match(usage).group(1).split(',')

    def do_handler(command):
      def handler(self, args):
        try:
          parsed = parser.parse_args([command] + shlex.split(args))
          parsed.func(parsed)
        except:
          pass
      return handler

    def help_handler(command):
      def handler(self):
        try:
          parser.parse_args([command, '--help'])
        except:
          pass
      return handler

    for command in commands:
      setattr(cls, 'do_' + command, do_handler(command))
      setattr(cls, 'help_' + command, help_handler(command))

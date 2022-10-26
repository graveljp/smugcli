"""Interactive shell for running smugcli commands."""

import cmd
import shlex
import re


class Error(Exception):
  """Base class for all exception of this module."""


class InitializationError(Error):
  """Raised if shell can't be initialized."""


class SmugMugShell(cmd.Cmd):
  """Interactive shell for running smugcli commands."""

  intro = 'Welcome to the SmugMug shell.   Type help or ? to list commands.\n'
  prompt = '(smugmug) '
  file = None
  _cmd_list_re = re.compile(r'.*\{([a-z,]+)\}', re.DOTALL)

  def __init__(self, fs):
    cmd.Cmd.__init__(self)
    self._fs = fs

  def do_exit(self, arg):
    """Exit the shell."""
    del arg  # Unused.
    return True

  @classmethod
  def set_parser(cls, parser):
    """Configure the shell from the specified parser's commands."""
    usage = parser.format_usage()
    matches = SmugMugShell._cmd_list_re.match(usage)
    if matches is None:
      raise InitializationError(
          'Failed creating shell commands from `smugcli` parser.')
    commands = matches.group(1).split(',')

    def do_handler(command):
      def handler(self, args):
        del self  # Unused.
        try:
          parsed = parser.parse_args([command] + shlex.split(args))
          parsed.func(parsed)
        except Exception as exc:  # pylint: disable=broad-except
          print(f'Command failed: {exc}')
      return handler

    def help_handler(command):
      def handler(self):
        del self  # Unused.
        try:
          parser.parse_args([command, '--help'])
        except Exception as exc:  # pylint: disable=broad-except
          print(f'Command failed: {exc}')
      return handler

    for command in commands:
      setattr(cls, 'do_' + command, do_handler(command))
      setattr(cls, 'help_' + command, help_handler(command))

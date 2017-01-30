# Interactive shell for running smugcli commands

import cmd

class SmugMugShell(cmd.Cmd):
  intro = 'Welcome to the SmugMug shell.   Type help or ? to list commands.\n'
  prompt = '(smugmug) '
  file = None

  def __init__(self, smugmug):
    cmd.Cmd.__init__(self)
    self._smugmug = smugmug

  @classmethod
  def set_commands(cls, commands):
    def build_handler(callback):
      def handler(self, args):
        try:
          callback(self._smugmug, args.split())
        except:
          pass
      return handler

    for command, callback in commands.iteritems():
      setattr(cls, 'do_' + command, build_handler(callback))

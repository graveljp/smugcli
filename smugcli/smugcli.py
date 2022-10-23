#!/usr/bin/python
# Command line tool for SmugMug. Uses SmugMug API V2.

import sys

if sys.version_info < (3, 7, 0):
  print('SmugCLI requires Python version 3.7 or above.')
  sys.exit(1)


from . import smugcli_commands

def main():
  smugcli_commands.run(sys.argv[1:])

if __name__ == '__main__':
  main()

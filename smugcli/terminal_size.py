#!/usr/bin/env python3

"""Returns the size of the terminal we are running in."""

# Source: https://gist.github.com/jtriley/1108174

import os
import shlex
import struct
import pkgutil
import platform
import subprocess
from typing import Tuple


def get_terminal_size() -> Tuple[int, int]:
  """Returns the size of the terminal console we are running in.
  Works on Linux, Os X, Windows and Cygwin

  Originally retrieved from:
  http://stackoverflow.com/questions/566746/how-to-get-console-window-width-in-python
  """
  tuple_xy = None
  current_os = platform.system()
  if current_os == 'Windows':
    tuple_xy = _get_terminal_size_windows()
    if tuple_xy is None:
      # Needed for Window's Python in Cygwin's xterm.
      tuple_xy = _get_terminal_size_tput()
  if current_os in ['Linux', 'Darwin'] or current_os.startswith('CYGWIN'):
    tuple_xy = _get_terminal_size_linux()
  if tuple_xy is None or any(not i for i in tuple_xy):
    tuple_xy = (80, 25)
  return tuple_xy


def _get_terminal_size_windows():
  try:
    # stdin handle is -10
    # stdout handle is -11
    # stderr handle is -12
    windll = pkgutil.resolve_name('ctypes.windll')
    create_string_buffer = pkgutil.resolve_name('ctypes.create_string_buffer')
    handle = windll.kernel32.GetStdHandle(-12)
    buffer = create_string_buffer(22)
    res = windll.kernel32.GetConsoleScreenBufferInfo(handle, buffer)
    if res:
      (buf_x, buf_y, cur_x, cur_y, attr,  # pylint: disable=unused-variable
       left, top, right, bottom,
       max_x, max_y  # pylint: disable=unused-variable
       ) = struct.unpack("hhhhHhhhhhh", buffer.raw)
      size_x = right - left + 1
      size_y = bottom - top + 1
      return size_x, size_y
  except Exception:  # pylint: disable=broad-except
    pass
  return None


def _get_terminal_size_tput():
  # get terminal width
  # src: http://stackoverflow.com/questions/263890/how-do-i-find-the-width-height-of-a-terminal-window  # pylint: disable=line-too-long  # noqa: E501
  try:
    cols = int(subprocess.check_call(shlex.split('tput cols')))
    rows = int(subprocess.check_call(shlex.split('tput lines')))
    return (cols, rows)
  except Exception:  # pylint: disable=broad-except
    return None


def _get_terminal_size_linux():
  def ioctl_gwinsz(file):
    try:
      return struct.unpack(
          'hh', pkgutil.resolve_name('fcntl.ioctl')(
              file, pkgutil.resolve_name('termios.TIOCGWINSZ'), '1234'))
    except Exception:  # pylint: disable=broad-except
      pass
  size = ioctl_gwinsz(0) or ioctl_gwinsz(1) or ioctl_gwinsz(2)
  if not size:
    try:
      file = os.open(pkgutil.resolve_name('os.ctermid')(), os.O_RDONLY)
      size = ioctl_gwinsz(file)
      os.close(file)
    except Exception:  # pylint: disable=broad-except
      pass
  if not size:
    try:
      size = (os.environ['LINES'], os.environ['COLUMNS'])
    except Exception:  # pylint: disable=broad-except
      return None
  return int(size[1]), int(size[0])


def main():
  """Prints the terminal size."""
  size_x, size_y = get_terminal_size()
  print('width =', size_x, 'height =', size_y)


if __name__ == "__main__":
  main()

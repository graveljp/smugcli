"""
Context manager object intercepting writes to stdout and making sure lines
are written atomically. This ensures that two lines printed by two different
threads won't be printed entangled with each other.
"""

import io
import os
import threading

from . import stdout_interceptor


thread_local = threading.local()


class ThreadSafePrint(stdout_interceptor.StdoutInterceptor):
  """Context manager allow multiple threads to print to the same console.

  When used in a `with:` statement, ThreadSafePrint replaces the global
  stdout, intercepting all writes and making sure lines are written atomically.
  This ensures that two lines printed by two different threads won't be
  printed entangled with each other.
  """

  def __init__(self):
    super().__init__()
    self._mutex = threading.Lock()

  def write(self, string):
    """Write a string to stdout."""
    if not hasattr(thread_local, 'stdout'):
      thread_local.stdout = io.StringIO()
    stdout = thread_local.stdout

    stdout.write(string.decode('utf-8')
                 if isinstance(string, bytes) else string)
    stdout.seek(0)
    lines = stdout.readlines()
    stdout.seek(0)
    stdout.truncate()
    with self._mutex:
      for line in lines:
        if '\n' in line:
          # There is a strange bug where if multiple threads print at the same
          # time, some of the printed lines get's prefixed with a whitespace. I
          # could not find where that space is coming from, so I'm stripping it
          # away for now.
          super().stdout.write(line.strip() + os.linesep)
        elif '\r' in line:
          super().stdout.write(line)
          super().stdout.flush()
        else:
          stdout.write(line)
          break

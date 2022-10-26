"""
Context manager object intercepting writes to stdout and making sure lines
are written atomically. This ensures that two lines printed by two different
threads won't be printed entangled with each other.
"""

import io
import os
import sys
import threading


thread_local = threading.local()


class Error(Exception):
  """Base class for all exception of this module."""


class InvalidUsageError(Error):
  """Error raised on incorrect API uses."""


class ThreadSafePrint(object):
  """Context manager allow multiple threads to print to the same console.

  When used in a `with:` statement, ThreadSafePrint replaces the global
  stdout, intercepting all writes and making sure lines are written atomically.
  This ensures that two lines printed by two different threads won't be
  printed entangled with each other.
  """

  def __init__(self):
    self._original_stdout = None
    self._mutex = threading.Lock()


  def __enter__(self):
    self._original_stdout = sys.stdout
    sys.stdout = self
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    del exc_type, exc_value, traceback  # Unused.
    if self._original_stdout is None:
      raise InvalidUsageError(
          "Object must be used as a context manager, in a `with:` statement.")
    sys.stdout = self._original_stdout

  def write(self, string):
    """Write a string to stdout."""
    if self._original_stdout is None:
      raise InvalidUsageError(
          "Object must be used as a context manager, in a `with:` statement.")
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
          self._original_stdout.write(line.strip() + os.linesep)
        elif '\r' in line:
          self._original_stdout.write(line)
          self._original_stdout.flush()
        else:
          stdout.write(line)
          break

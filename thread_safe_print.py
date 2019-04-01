# Guard object intercepting writes to stdout and making sure lines are written
# atomically. This ensures that two lines won't be printed entangled with
# each other.

import os
import six
import sys
import threading


thread_local = threading.local()


class ThreadSafePrint(object):

  def __enter__(self):
    self._original_stdout = sys.stdout
    self._mutex = threading.Lock()
    sys.stdout = self
    return self

  def __exit__(self, type, value, traceback):
    sys.stdout = self._original_stdout

  def write(self, string):
    if not hasattr(thread_local, 'stdout'):
      thread_local.stdout = six.StringIO()
    stdout = thread_local.stdout

    stdout.write(string.decode('utf-8')
                 if isinstance(string, six.binary_type) else string)
    stdout.seek(0)
    lines = stdout.readlines()
    stdout.seek(0)
    stdout.truncate()
    with self._mutex:
      for line in lines:
        if '\n' in line:
          # There is a strange bug where if multiple threads print at the same
          # time, some of the printed lines get's prefixed with a whitepace. I
          # could not find where that space is comming from, so I'm stripping it
          # away for now.
          self._original_stdout.write(line.strip() + os.linesep)
        elif '\r' in line:
          self._original_stdout.write(line)
          self._original_stdout.flush()
        else:
          stdout.write(line)
          break

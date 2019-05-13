from . import terminal_size

import collections
import os
import sys
import time
import threading

if os.name == 'nt':
  import colorama
  colorama.init()


class TaskGuard(object):
  def __init__(self, task_manager, category, task, status=''):
    self._task_manager = task_manager
    self._category = category
    self._task = task
    self._task_manager.update_progress(category, task, status)

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self._task_manager.task_completed(self._category, self._task)


class TaskManager(object):

  def __init__(self):
    self._tasks_in_progress = collections.defaultdict(dict)
    self._mutex = threading.RLock()
    self._last_update_time = 0

  def __enter__(self):
    self._original_stdout = sys.stdout
    sys.stdout = self
    return self

  def __exit__(self, type, value, traceback):
    with self._mutex:
      sys.stdout = self._original_stdout
      self._original_stdout.write('\033[J')

  def write(self, string):
    with self._mutex:
      self._original_stdout.write('\033[J' + string + self.get_status_string())
      self._original_stdout.flush()
      self._last_update_time = time.time()

  def start_task(self, category, task, status=''):
    return TaskGuard(self, category, task, status)

  def update_progress(self, category, task, status=''):
    with self._mutex:
      self._tasks_in_progress[category][task] = status
      if time.time() > self._last_update_time + 0.05:
        self.print_status()

  def task_completed(self, category, task):
    with self._mutex:
      del self._tasks_in_progress[category][task]
      if not self._tasks_in_progress[category]:
        del self._tasks_in_progress[category]
        self.print_status()

  def get_status_string(self):
    terminal_width = terminal_size.get_terminal_size()[0] - 1
    with self._mutex:
      text = (
        os.linesep +
        (os.linesep * 2).join(
          os.linesep.join(self._clip_long_line('%s%s' % (t, s), terminal_width)
                          for t, s in sorted(tasks.items()))
          for _, tasks in sorted(self._tasks_in_progress.items())) +
        os.linesep)
      return text + '\033[%dA\r' % (len(text.split(os.linesep))-1)

  def print_status(self):
    self.write('')

  def _clip_long_line(self, string, max_length):
    if len(string) > max_length:
      clipped = '...'
      prefix = int(max_length * 5 / 8)
      suffix = len(string) - (max_length - prefix - len(clipped))
      return string[:prefix] + clipped + string[suffix:]
    else:
      return string

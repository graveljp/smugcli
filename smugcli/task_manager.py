"""Context manager replacing global stdout & maintain task status on screen."""

import collections
import os
import platform
import sys
import time
import threading

from . import stdout_interceptor
from . import terminal_size

if platform.system() == 'Windows':
  import colorama  # pylint: disable=import-error
  colorama.init()


class Task():
  """Context manager maintaining a task status on screen until it exits."""

  def __init__(self,
               task_manager: 'TaskManager',
               category: int,
               task: str,
               status: str = ''):
    self._task_manager = task_manager
    self._category = category
    self._task = task
    self._task_manager.update_status(category, task, status)

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    del exc_type, exc_value, traceback  # Unused.
    self._task_manager.task_completed(self._category, self._task)

  def update_status(self, status: str = '') -> None:
    """Update the progress string for this task."""
    self._task_manager.update_status(self._category, self._task, status)


class TaskManager(stdout_interceptor.StdoutInterceptor):
  """Context manager replacing global stdout to maintain task status on screen.

  TaskManager is used to allow many threads to write to stdout simultaneously,
  while maintaining status messages printed after the last text written.
  On each write, the status messages are erased, the new text is written, and
  the status message is re-printed.

  Each status message lines correspond to an ongoing task. Tasks are also
  context managers, implemented by the class `Task`. Once a task is started,
  its status string will be maintained on screen until it's completed.

  Task status lines are grouped by categories. The categories are just
  numbers: tasks with a smaller category number get their status printed before
  those with a larger category.

  Example usage:

    with task_manager.TaskManager() as manager:

      # On thread 1
      with manager.start_task(category=0, task='First task') as task1:
        task1.update_status(': 33%')
        print("Foo")
        task1.update_status(': 67%')
        print("Bar")
        task1.update_status(': 100%')

      # On thread 2
      with manager.start_task(category=1, 'Second task') as task2:
        task2.update_status(': 50%')
        task2.update_status(': 100%')

  In this example, the shell will update to display something like this:

  Before any of the `update_status` is reached:
    First task
    Second task

  After the first `update_status` is reached:
    First task: 33%
    Second task: 50%

  When 'Foo' gets printed:
    Foo
    First task: 33%
    Second task: 50%

  After some more progress:
    Foo
    First task: 67%
    Second task: 50%

  When 'Bar' gets printed:
    Bar
    First task: 67%
    Second task: 50%

  After last `update_status`:
    Bar
    Foo
    First task: 100%
    Second task: 100%

  After the context managers exits:
    Bar
    Foo
  """

  def __init__(self):
    super().__init__()
    self._tasks_in_progress = collections.defaultdict(dict)
    self._mutex = threading.RLock()
    self._last_update_time = 0

  def __exit__(self, exc_type, exc_value, traceback) -> None:
    """Terminate this TaskManager and restore global stdout."""
    super().__exit__(exc_type, exc_value, traceback)
    sys.stdout.write('\033[J')

  def write(self, string: str) -> None:
    """Erase previous status, prints the specified text and re-print status."""
    # Clear the end of each terminal lines before moving to the next line.
    endline = '\033[K' + os.linesep
    string = endline.join(string.split(os.linesep))

    with self._mutex:
      super().stdout.write(string + self.get_status_string())
      super().stdout.flush()
      self._last_update_time = time.time()

  def start_task(self, category: int, task: str, status: str = '') -> Task:
    """Start a task whose status string will be maintained on screen."""
    return Task(self, category, task, status)

  def update_status(
      self, category: int, task: str, status: str = ''
  ) -> None:
    """Update the status of a task"""
    with self._mutex:
      self._tasks_in_progress[category][task] = status
      if time.time() > self._last_update_time + 0.05:
        self.print_status()

  def task_completed(self, category: int, task: str) -> None:
    """Mark a task as complete and stop printing its status."""
    with self._mutex:
      del self._tasks_in_progress[category][task]
      if not self._tasks_in_progress[category]:
        del self._tasks_in_progress[category]
        self.print_status()

  def get_status_string(self) -> str:
    """Generate a string containing all tasks' status."""
    terminal_width = terminal_size.get_terminal_size()[0] - 1

    # Clear the end of each console line before moving to the next line.
    endline = '\033[K' + os.linesep

    with self._mutex:
      text = (
          endline +
          (endline * 2).join(
              endline.join(self.clip_long_line(f'{t}{s}', terminal_width)
                           for t, s in sorted(tasks.items()))
              for _, tasks in sorted(self._tasks_in_progress.items())) +
          endline)

      # Print the status text, clear the remaining of the console and move
      # the cursor up to the first status line, ready for the next print.
      return text + '\033[J' + f'\033[{len(text.split(os.linesep))-1}A\r'

  def print_status(self) -> None:
    """Refresh the status in the shell."""
    self.write('')

  def clip_long_line(self, string: str, max_length: int) -> str:
    """Clip long lines to `max_length` by replacing a section with '...'."""
    if len(string) > max_length:
      clipped = '...'
      prefix = int(max_length * 5 / 8)
      suffix = len(string) - (max_length - prefix - len(clipped))
      return string[:prefix] + clipped + string[suffix:]
    return string

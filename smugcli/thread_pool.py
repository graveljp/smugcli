"""Pool of threads consuming tasks from a queue"""

import queue
import threading
import time


class Worker(threading.Thread):
  """Worker thread processing tasks."""

  def __init__(self, thread_pool, task_queue):
    super().__init__()
    self._task_queue = task_queue
    self._thread_pool = thread_pool

  def run(self):
    while True:
      try:
        func, args, kwargs = self._task_queue.get(timeout=1)
        try:
          if func:
            func(*args, **kwargs)
        except Exception as exc:  # pylint: disable=broad-except
          print(str(exc))
        finally:
          self._task_queue.task_done()
      except queue.Empty:
        pass

      if self._thread_pool.aborting:
        return


class ThreadPool:
  """Pool of threads consuming tasks from a queue"""

  def __init__(self, num_threads: int) -> None:
    self._tasks = queue.Queue(num_threads)
    self._threads = []
    self._aborting = False
    for _ in range(num_threads):
      worker = Worker(self, self._tasks)
      worker.daemon = True
      worker.start()
      self._threads.append(worker)

  @property
  def aborting(self):
    """Returns whether the threadpool is aborting."""
    return self._aborting

  def add(self, func, *args, **kwargs) -> None:
    """Add a task thread pool.

    Args:
      func: function to be executed in the thread pool.
      args: argument list for `func`.
      kwargs: keyword arguments for `func`.
    """
    self._tasks.put((func, args, kwargs))

  def join(self) -> None:
    """Wait for all the tasks to be executed in the thread pool."""

    # Busy-loop instead of using 'join' to allow for ctrl-C interrupts.
    while not self._tasks.empty():
      time.sleep(1)

    self._stop_workers()

    # Wait for all threads to quit.
    for thread in self._threads:
      while thread.is_alive():
        thread.join(1)

  def _stop_workers(self, signum=None, frame=None):
    del signum, frame  # Unused.
    self._aborting = True

    # Wake up any remaining blocked threads.
    for _ in self._threads:
      try:
        self._tasks.put((None, None, None), block=False)
      except queue.Full:
        pass

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    del exc_type, exc_value, traceback  # Unused.
    self.join()

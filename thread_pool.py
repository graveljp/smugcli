import six
from six.moves import queue
import threading
import time
#import traceback


class Worker(threading.Thread):
  """Worker thread processing tasks."""

  def __init__(self, thread_pool, task_queue):
    super(Worker, self).__init__()
    self._task_queue = task_queue
    self._thread_pool = thread_pool

  def run(self):
    while True:
      try:
        func, args, kwargs = self._task_queue.get(timeout=1)
        try:
          if func:
            func(*args, **kwargs)
        except Exception as e:
          print(six.text_type(e))
          # traceback.print_exc()
        finally:
          self._task_queue.task_done()
      except queue.Empty as e:
        pass

      if self._thread_pool.aborting:
        return


class ThreadPool:
  """Pool of threads consuming tasks from a queue"""
  def __init__(self, num_threads):
    self._tasks = queue.Queue(num_threads)
    self._threads = []
    self._aborting = False
    for _ in range(num_threads):
      t = Worker(self, self._tasks)
      t.daemon = True
      t.start()
      self._threads.append(t)

  @property
  def aborting(self):
    return self._aborting

  def add(self, func, *args, **kwargs):
    """Add a task thread pool.

    Args:
      func: function to be executed in the thead pool.
      args: argument list for `func`.
      kwargs: keyword arguments for `func`.
    """
    self._tasks.put((func, args, kwargs))

  def join(self):
    """Wait for all the tasks to be executed in the thread pool."""

    # Buzy-loop instead of using 'join' to allow for ctrl-C interrupts.
    while not self._tasks.empty():
      time.sleep(1)

    self._stop_workers()

    # Wait for all threads to quit.
    for t in self._threads:
      while t.is_alive():
        t.join(1)

  def _stop_workers(self, signum=None, frame=None):
    self._aborting = True

    # Wake up any remaining blocked threads.
    for t in self._threads:
      try:
        self._tasks.put((None, None, None), block=False)
      except queue.Full as e:
        pass

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.join()

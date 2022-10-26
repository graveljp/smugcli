"""Tests for thread_pool.py."""

import unittest
import queue
import sys

import io_expectation as expect

from smugcli import thread_pool


class TestThreadPool(unittest.TestCase):
  """Tests for the `thread_pool.ThreadPool` class."""

  def _producer_thread(self, results):
    for i in range(10):
      results.put(i)

  def _consumer_thread(self, results):
    for i in range(10):
      self.assertEqual(results.get(), i)

  def test_context_manager(self):
    """Tests the ThreadPool when used in a context manager."""
    results = queue.Queue(maxsize=1)
    with thread_pool.ThreadPool(2) as pool:
      pool.add(self._producer_thread, results)
      pool.add(self._consumer_thread, results)

  def test_join(self):
    """Tests the `join` method."""
    results = queue.Queue(maxsize=1)
    pool = thread_pool.ThreadPool(2)
    pool.add(self._producer_thread, results)
    pool.add(self._consumer_thread, results)
    pool.join()

  def test_exception(self):
    """Tests exceptions in threads."""
    mock_io = expect.ExpectedInputOutput()
    sys.stdout = mock_io

    def will_raise():
      raise Exception('Unicode: \xe2')

    with thread_pool.ThreadPool(2) as pool:
      pool.add(will_raise)

    mock_io.assert_output_was('Unicode: \xe2')

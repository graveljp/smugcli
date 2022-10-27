"""Tests for thread_safe_print.py"""

import queue
import sys
import unittest

import io_expectation as expect

from smugcli import thread_pool, thread_safe_print


class TestThreadSafePrint(unittest.TestCase):
  """Test for the `thread_safe_print.ThreadSafePrint` class."""

  def _thread1(self, thread1_turn, thread2_turn):
    thread1_turn.get()
    sys.stdout.write('Thread 1 starts, ')
    thread2_turn.put(True)

    thread1_turn.get()
    sys.stdout.write('thread 1 finishes.')
    thread2_turn.put(True)

    thread1_turn.get()
    sys.stdout.write('\n')
    thread2_turn.put(True)

  def _thread2(self, thread1_turn, thread2_turn):
    thread2_turn.get()
    sys.stdout.write('Thread 2 starts, ')
    thread1_turn.put(True)

    thread2_turn.get()
    sys.stdout.write('thread 2 finishes.')
    thread1_turn.put(True)

    thread2_turn.get()
    sys.stdout.write('\n')

  def test_multi_threaded_interleaved_write(self):
    """Tests that multi-threaded interleaved I/Os get printed correctly."""
    mock_io = expect.ExpectedInputOutput()
    sys.stdout = mock_io

    thread1_turn = queue.Queue()
    thread2_turn = queue.Queue()
    thread1_turn.put(True)
    with thread_safe_print.ThreadSafePrint():
      with thread_pool.ThreadPool(2) as pool:
        pool.add(self._thread1, thread1_turn, thread2_turn)
        pool.add(self._thread2, thread1_turn, thread2_turn)

    mock_io.assert_output_was([
        'Thread 1 starts, thread 1 finishes.',
        'Thread 2 starts, thread 2 finishes.'
    ])

"""Unit test for task_manager.py."""

import datetime
import itertools
import sys
from typing import Sequence
import unittest

import freezegun
from parameterized import parameterized

import io_expectation as expect
from smugcli import task_manager


class TaskManagerTests(unittest.TestCase):
  """Unit tests for the TaskManager class."""

  def except_status(self, status_string: Sequence[str]) -> expect.InOrder:
    """Builds an expectation checking that `status_string` will be printed."""
    expect_escape = expect.Regex(r'\033\[J|'
                                 r'\033\[K|'
                                 r'\033\[\d+A|'
                                 r'\n|'
                                 r'\r').repeatedly()
    return expect.InOrder([expect_escape] +
                          list(itertools.chain.from_iterable(
                              [s, expect_escape] for s in status_string)))

  def test_update_progress(self):
    """Tests that status strings are printed, but not if they go too fast."""
    expected_io = expect.ExpectedInputOutput()
    sys.stdout = expected_io
    with freezegun.freeze_time('2019-01-01 12:00:00') as frozen_time:
      with task_manager.TaskManager() as manager:
        with manager.start_task(category=0, task='Some task') as task:
          frozen_time.tick(delta=datetime.timedelta(milliseconds=1))
          task.update_status(': 25%')
          frozen_time.tick(delta=datetime.timedelta(milliseconds=100))
          task.update_status(': 50%')
          frozen_time.tick(delta=datetime.timedelta(milliseconds=1))
          task.update_status(': 75%')

    expected_io.assert_output_was(self.except_status(['Some task',
                                                      'Some task: 50%']))

  def test_task_groups(self):
    """Test task grouping."""
    expected_io = expect.ExpectedInputOutput()
    sys.stdout = expected_io
    with freezegun.freeze_time('2019-01-01 12:00:00') as frozen_time:
      with task_manager.TaskManager() as manager:
        with manager.start_task(0, 'Task 0') as task0:
          expected_io.assert_output_was(self.except_status(['Task 0']))

          frozen_time.tick(delta=datetime.timedelta(milliseconds=100))
          with manager.start_task(1, 'Task 1') as task1:
            expected_io.assert_output_was(self.except_status(['Task 0',
                                                              'Task 1']))

            frozen_time.tick(delta=datetime.timedelta(milliseconds=100))
            task0.update_status(': 50%')
            expected_io.assert_output_was(self.except_status(['Task 0: 50%',
                                                              'Task 1']))

            frozen_time.tick(delta=datetime.timedelta(milliseconds=100))
            task1.update_status(': 75%')
            expected_io.assert_output_was(self.except_status(['Task 0: 50%',
                                                              'Task 1: 75%']))

          expected_io.assert_output_was(self.except_status(['Task 0: 50%']))
        expected_io.assert_output_was(self.except_status([]))

  @parameterized.expand([
      ('1234567890123456789', '1234567890123456789'),
      ('12345678901234567890', '12345678901234567890'),
      ('123456789012345678901', '123456789012...78901')])
  def test_clip_long_line(self, line, expected):
    """Test long line clipping."""
    manager = task_manager.TaskManager()
    self.assertEqual(manager.clip_long_line(line, 20), expected)


if __name__ == '__main__':
  unittest.main()

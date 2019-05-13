from smugcli import task_manager

import io_expectation as expect

import datetime
import freezegun
import itertools
from parameterized import parameterized
import sys
import unittest

class TaskManagerTests(unittest.TestCase):

  def except_status(self, status_string):
    expect_escape = expect.Regex(r'\033\[J|'
                                 r'\033\[\d+A|'
                                 r'\n|'
                                 r'\r').repeatedly()
    return expect.InOrder([expect_escape] +
                          list(itertools.chain.from_iterable(
                            [s, expect_escape] for s in status_string)))

  def test_update_progress(self):
    io = expect.ExpectedInputOutput()
    sys.stdout = io
    with freezegun.freeze_time('2019-01-01 12:00:00') as frozen_time:
      with task_manager.TaskManager() as manager:
        with manager.start_task(0, 'Some task'):
          frozen_time.tick(delta=datetime.timedelta(milliseconds=1))
          manager.update_progress(0, 'Some task', ': 25%')
          frozen_time.tick(delta=datetime.timedelta(milliseconds=100))
          manager.update_progress(0, 'Some task', ': 50%')
          frozen_time.tick(delta=datetime.timedelta(milliseconds=1))
          manager.update_progress(0, 'Some task', ': 75%')

    io.assert_output_was(self.except_status(['Some task',
                                             'Some task: 50%']))

  def test_task_groups(self):
    io = expect.ExpectedInputOutput()
    sys.stdout = io
    with freezegun.freeze_time('2019-01-01 12:00:00') as frozen_time:
      with task_manager.TaskManager() as manager:
        with manager.start_task(0, 'Task 0'):
          io.assert_output_was(self.except_status(['Task 0']))

          frozen_time.tick(delta=datetime.timedelta(milliseconds=100))
          with manager.start_task(1, 'Task 1'):
            io.assert_output_was(self.except_status(['Task 0',
                                                     'Task 1']))

            frozen_time.tick(delta=datetime.timedelta(milliseconds=100))
            manager.update_progress(0, 'Task 0', ': 50%')
            io.assert_output_was(self.except_status(['Task 0: 50%',
                                                     'Task 1']))

            frozen_time.tick(delta=datetime.timedelta(milliseconds=100))
            manager.update_progress(1, 'Task 1', ': 75%')
            io.assert_output_was(self.except_status(['Task 0: 50%',
                                                     'Task 1: 75%']))

          io.assert_output_was(self.except_status(['Task 0: 50%']))
        io.assert_output_was(self.except_status([]))

  @parameterized.expand([
      ('1234567890123456789', '1234567890123456789'),
      ('12345678901234567890', '12345678901234567890'),
      ('123456789012345678901', '123456789012...78901')])
  def test_clip_long_line(self, line, expected):
    manager = task_manager.TaskManager()
    self.assertEqual(manager._clip_long_line(line, 20), expected)


if __name__ == '__main__':
  unittest.main()

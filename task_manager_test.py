import task_manager

from parameterized import parameterized
import unittest

class TaskManagerTests(unittest.TestCase):
  @parameterized.expand([
      ('1234567890123456789', '1234567890123456789'),
      ('12345678901234567890', '12345678901234567890'),
      ('123456789012345678901', '123456789012...78901')])
  def test_clip_long_line(self, line, expected):
    manager = task_manager.TaskManager()
    self.assertEqual(manager._clip_long_line(line, 20), expected)


if __name__ == '__main__':
  unittest.main()

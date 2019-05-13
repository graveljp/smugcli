from smugcli import smugmug

import test_utils

import freezegun
import unittest

class MockNode(object):
  def __init__(self):
    self._reset_times = 0

  def reset_cache(self):
    self._reset_times += 1


class TestChildCacheGarbageCollector(unittest.TestCase):

  def test_clears_child_cache(self):
    gc = smugmug.ChildCacheGarbageCollector(3)
    nodes = [MockNode(), MockNode(), MockNode(), MockNode(), MockNode()]
    gc.visited(nodes[0])
    gc.visited(nodes[1])
    gc.visited(nodes[2])
    gc.visited(nodes[3])
    gc.visited(nodes[4])

    self.assertEqual(nodes[0]._reset_times, 1)
    self.assertEqual(nodes[1]._reset_times, 1)
    self.assertEqual(nodes[2]._reset_times, 0)
    self.assertEqual(nodes[3]._reset_times, 0)
    self.assertEqual(nodes[4]._reset_times, 0)

  def test_repeated_visit_are_ignored(self):
    gc = smugmug.ChildCacheGarbageCollector(2)
    nodes = [MockNode(), MockNode(), MockNode()]
    gc.visited(nodes[0])
    gc.visited(nodes[1])
    gc.visited(nodes[2])
    gc.visited(nodes[2])
    gc.visited(nodes[2])

    self.assertEqual(nodes[0]._reset_times, 1)
    self.assertEqual(nodes[1]._reset_times, 0)
    self.assertEqual(nodes[2]._reset_times, 0)

  def test_optimally_resets_alternating_nodes(self):
    gc = smugmug.ChildCacheGarbageCollector(2)

    nodes = [MockNode(), MockNode()]
    gc.visited(nodes[1])
    gc.visited(nodes[0])
    gc.visited(nodes[1])
    gc.visited(nodes[0])

    self.assertEqual(nodes[0]._reset_times, 0)
    self.assertEqual(nodes[1]._reset_times, 0)

  def test_heap_does_not_grow_out_of_control(self):
    gc = smugmug.ChildCacheGarbageCollector(1)

    node = MockNode()
    gc.visited(node)
    gc.visited(node)
    gc.visited(node)
    gc.visited(node)

    self.assertEqual(len(gc._nodes), 1)
    self.assertEqual(len(gc._oldest), 1)

  def test_time_keyed_heap_works_with_nodes_created_on_same_timestamp(self):
    with freezegun.freeze_time('2019-01-01') as frozen_time:
      gc = smugmug.ChildCacheGarbageCollector(1)
      nodes = [MockNode(), MockNode(), MockNode()]

      gc.visited(nodes[0])
      gc.visited(nodes[1])

      frozen_time.tick()
      gc.visited(nodes[2])

    self.assertEqual(nodes[0]._reset_times, 1)
    self.assertEqual(nodes[1]._reset_times, 1)
    self.assertEqual(nodes[2]._reset_times, 0)

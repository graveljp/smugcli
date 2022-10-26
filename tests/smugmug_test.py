"""Unit test for smugmug.py"""

import unittest

import freezegun

from smugcli import smugmug


class MockNode(object):
  """A mock version of `smugmug.Node`."""

  def __init__(self):
    self._reset_count = 0

  def reset_cache(self):
    """Override of `smugmug.Node.reset_cache`, tracking invocation count."""
    self._reset_count += 1

  @property
  def reset_count(self):
    """Returns the number of time `reset_cache` was called on this node."""
    return self._reset_count


class TestChildCacheGarbageCollector(unittest.TestCase):
  """Test for `smugmug.ChildCacheGarbageCollector`."""

  def test_clears_child_cache(self):
    """Tests that nodes get reset, oldest visited first."""
    collector = smugmug.ChildCacheGarbageCollector(3)
    nodes = [MockNode(), MockNode(), MockNode(), MockNode(), MockNode()]
    collector.visited(nodes[0])
    collector.visited(nodes[1])
    collector.visited(nodes[2])
    collector.visited(nodes[3])
    collector.visited(nodes[4])

    self.assertEqual(nodes[0].reset_count, 1)
    self.assertEqual(nodes[1].reset_count, 1)
    self.assertEqual(nodes[2].reset_count, 0)
    self.assertEqual(nodes[3].reset_count, 0)
    self.assertEqual(nodes[4].reset_count, 0)

  def test_repeated_visit_are_ignored(self):
    """Tests that repeating visits do not count."""
    collector = smugmug.ChildCacheGarbageCollector(2)
    nodes = [MockNode(), MockNode(), MockNode()]
    collector.visited(nodes[0])
    collector.visited(nodes[1])
    collector.visited(nodes[2])
    collector.visited(nodes[2])
    collector.visited(nodes[2])

    self.assertEqual(nodes[0].reset_count, 1)
    self.assertEqual(nodes[1].reset_count, 0)
    self.assertEqual(nodes[2].reset_count, 0)

  def test_optimally_resets_alternating_nodes(self):
    """Tests that alternating visits do not count."""
    collector = smugmug.ChildCacheGarbageCollector(2)

    nodes = [MockNode(), MockNode()]
    collector.visited(nodes[1])
    collector.visited(nodes[0])
    collector.visited(nodes[1])
    collector.visited(nodes[0])

    self.assertEqual(nodes[0].reset_count, 0)
    self.assertEqual(nodes[1].reset_count, 0)

  def test_heap_does_not_grow_out_of_control(self):
    """Tests garbage collector's memory usage."""
    collector = smugmug.ChildCacheGarbageCollector(1)

    node = MockNode()
    collector.visited(node)
    collector.visited(node)
    collector.visited(node)
    collector.visited(node)

    self.assertEqual(len(collector.nodes), 1)
    self.assertEqual(len(collector.oldest), 1)

  def test_time_keyed_heap_works_with_nodes_created_on_same_timestamp(self):
    """Tests that nodes created on the same timestamps gets GCed the same."""
    with freezegun.freeze_time('2019-01-01') as frozen_time:
      collector = smugmug.ChildCacheGarbageCollector(1)
      nodes = [MockNode(), MockNode(), MockNode()]

      collector.visited(nodes[0])
      collector.visited(nodes[1])

      frozen_time.tick()
      collector.visited(nodes[2])

    self.assertEqual(nodes[0].reset_count, 1)
    self.assertEqual(nodes[1].reset_count, 1)
    self.assertEqual(nodes[2].reset_count, 0)

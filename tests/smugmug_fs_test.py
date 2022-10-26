"""Unit test for smugmug_fs.py."""

import io
import json
import locale
import os
import sys
import unittest

from parameterized import parameterized
import responses

import test_utils

from smugcli import smugmug
from smugcli import smugmug_fs


API_ROOT = 'https://api.smugmug.com'


class TestSmugMugFS(unittest.TestCase):
  """Tests for the `smugmug_fs.SmugMugFS` class."""

  def setUp(self):
    self._fs = smugmug_fs.SmugMugFS(smugmug.FakeSmugMug({'authuser': 'cmac'}))
    self._cmd_output = io.StringIO()
    sys.stdout = self._cmd_output

    test_utils.add_mock_requests(responses)

  def tearDown(self):
    sys.stdout = sys.__stdout__

  @responses.activate
  def test_get_root_node(self):
    """Tests the `get_root_node` method."""
    self.assertTrue(self._fs.get_root_node('cmac')['IsRoot'])

  @responses.activate
  def test_get_children(self):
    """Tests the `get_children` method."""
    root_node = self._fs.get_root_node('cmac')
    root_children = root_node.get_children()
    self.assertEqual(len(root_children), 17)
    folder_node = root_children[3]
    self.assertEqual(folder_node.name, 'Photography')
    self.assertEqual(folder_node['Name'], 'Photography')

    folder_children = folder_node.get_children()
    self.assertEqual(len(folder_children), 16)
    album_node = folder_children[0]
    self.assertEqual(album_node.name, 'San Francisco by helicopter 2014')
    self.assertEqual(album_node['Name'], 'San Francisco by helicopter 2014')

    album_children = album_node.get_children()
    self.assertEqual(len(album_children), 18)
    file_node = album_children[0]
    self.assertEqual(file_node.name, 'DSC_5752.jpg')
    self.assertEqual(file_node['FileName'], 'DSC_5752.jpg')

  @responses.activate
  def test_get_child(self):
    """Tests the `get_child` method."""
    root_node = self._fs.get_root_node('cmac')
    photography = root_node.get_child('Photography')
    self.assertIsNotNone(photography)
    if photography:
      self.assertEqual(photography['Name'], 'Photography')

    invalid_child = root_node.get_child('Missing folder')
    self.assertIsNone(invalid_child)

  @responses.activate
  def test_path_to_node(self):
    """Tests the `path_to_node` method."""
    matched_nodes, unmatched_dirs = self._fs.path_to_node('cmac', '')
    self.assertEqual(len(matched_nodes), 1)
    self.assertTrue(matched_nodes[0]['IsRoot'])
    self.assertEqual(unmatched_dirs, [])

    matched_nodes, unmatched_dirs = self._fs.path_to_node('cmac',
                                                          os.path.normpath('/'))
    self.assertEqual(len(matched_nodes), 1)
    self.assertTrue(matched_nodes[0]['IsRoot'])
    self.assertEqual(unmatched_dirs, [])

    matched_nodes, unmatched_dirs = self._fs.path_to_node('cmac', 'Photography')
    self.assertEqual(len(matched_nodes), 2)
    self.assertTrue(matched_nodes[0]['IsRoot'])
    self.assertEqual(matched_nodes[1].name, 'Photography')
    self.assertEqual(matched_nodes[1]['Name'], 'Photography')
    self.assertEqual(unmatched_dirs, [])

    matched_nodes, unmatched_dirs = self._fs.path_to_node(
        'cmac', os.path.normpath('/Photography'))
    self.assertEqual(matched_nodes[-1].name, 'Photography')
    self.assertEqual(matched_nodes[-1]['Name'], 'Photography')
    self.assertEqual(unmatched_dirs, [])

    matched_nodes, unmatched_dirs = self._fs.path_to_node(
        'cmac',
        os.path.normpath('/Photography/San Francisco by helicopter 2014'))
    self.assertEqual(len(matched_nodes), 3)
    self.assertTrue(matched_nodes[0]['IsRoot'])
    self.assertEqual(matched_nodes[1]['Name'], 'Photography')
    self.assertEqual(matched_nodes[2]['Name'],
                     'San Francisco by helicopter 2014')
    self.assertEqual(unmatched_dirs, [])

    matched_nodes, unmatched_dirs = self._fs.path_to_node(
        'cmac', os.path.normpath('/invalid1'))
    self.assertEqual(len(matched_nodes), 1)
    self.assertTrue(matched_nodes[0]['IsRoot'])
    self.assertEqual(unmatched_dirs, ['invalid1'])

    matched_nodes, unmatched_dirs = self._fs.path_to_node(
        'cmac', os.path.normpath('/Photography/invalid2'))
    self.assertEqual(len(matched_nodes), 2)
    self.assertTrue(matched_nodes[0]['IsRoot'])
    self.assertEqual(matched_nodes[1].name, 'Photography')
    self.assertEqual(matched_nodes[1]['Name'], 'Photography')
    self.assertEqual(unmatched_dirs, ['invalid2'])

  @responses.activate
  def test_get(self):
    """Tests the `get` method."""
    self._fs.get('/api/v2/node/zx4Fx')
    testdir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(testdir, 'testdata', 'root_node.json'),
              encoding=locale.getpreferredencoding()) as handle:
      self.assertEqual(json.loads(self._cmd_output.getvalue()),
                       json.load(handle))

  @parameterized.expand([
      ('/Photography/',
       'San Francisco by helicopter 2014\n'
       'SmugMug homepage slide show\n'
       'New Journal style: Big photos!\n'
       'Samples from my new 200-400\n'
       'Paris and San Francisco videos by night\n'
       'Jackson Hole\n'
       'San Francisco skyline\n'
       'Giant prints for SmugMug\'s walls\n'
       'Testing video on the new Canon 7D\n'
       'Pictures I loved from the week\n'
       'Baldy\'s first experiments with HDR\n'
       'Canon 30D versus Fuji S5 image comparisons\n'
       'Mac color tests\n'
       'Ofoto, Shutterfly, EZprints compared\n'
       'Printing services test prints\n'
       'Quantum Q Flash 5D\n'),

      ('/Photography/San Francisco by helicopter 2014',
       'DSC_5752.jpg\n'
       'DSC_5903.jpg\n'
       'DSC_5932.jpg\n'
       'DSC_5947.jpg\n'
       'DSC_5978.jpg\n'
       'SF by air for 48 inch print-5978.jpg\n'
       'DSC_6023.jpg\n'
       'DSC_6069.jpg\n'
       'DSC_6110.jpg\n'
       'DSC_5626.jpg\n'
       'DSC_5657.jpg\n'
       'Von Wong-2807.jpg\n'
       'Von Wong-009783.jpg\n'
       'Von Wong-009789.jpg\n'
       'Von Wong-009812.jpg\n'
       'Von Wong-009906.jpg\n'
       'DSC_4933.jpg\n'
       'Logan Leia wave pool.jpg\n'
       ),

      ('/Photography/invalid',
       '"invalid" not found in "/Photography".\n'
       ),

      ('/Photography/invalid\xef',
       '"invalid\xef" not found in "/Photography".\n'
       )])
  @responses.activate
  def test_ls(self, folder, expected_message):
    """Tests the `ls` method."""
    self._fs.ls(None, os.path.normpath(folder), False)
    self.assertEqual(
        self._cmd_output.getvalue(),
        os.path.normpath(expected_message))


if __name__ == '__main__':
  unittest.main()

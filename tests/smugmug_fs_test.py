from smugcli import smugmug
from smugcli import smugmug_fs

import test_utils

import json
import os
from parameterized import parameterized
import responses
from six.moves import StringIO
import sys
import unittest


API_ROOT = 'https://api.smugmug.com'


class TestSmugMugFS(unittest.TestCase):

  def setUp(self):
    self._fs = smugmug_fs.SmugMugFS(smugmug.FakeSmugMug({'authuser': 'cmac'}))
    self._cmd_output = StringIO()
    sys.stdout = self._cmd_output

    test_utils.add_mock_requests(responses)

  def tearDown(self):
    sys.stdout = sys.__stdout__

  @responses.activate
  def test_get_root_node(self):
    self.assertTrue(self._fs.get_root_node('cmac')['IsRoot'])

  @responses.activate
  def test_get_children(self):
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
    root_node = self._fs.get_root_node('cmac')
    photography = root_node.get_child('Photography')
    self.assertEqual(photography['Name'], 'Photography')

    invalid_child = root_node.get_child('Missing folder')
    self.assertIsNone(invalid_child)

  @responses.activate
  def test_path_to_node(self):
    matched_nodes, unmatched_dirs = self._fs.path_to_node('cmac', '')
    self.assertEqual(len(matched_nodes), 1)
    self.assertTrue(matched_nodes[0]['IsRoot'])
    self.assertEqual(unmatched_dirs, [])

    matched_nodes, ummatched_dirs = self._fs.path_to_node('cmac',
                                                          os.path.normpath('/'))
    self.assertEqual(len(matched_nodes), 1)
    self.assertTrue(matched_nodes[0]['IsRoot'])
    self.assertEqual(unmatched_dirs, [])

    matched_nodes, ummatched_dirs = self._fs.path_to_node('cmac', 'Photography')
    self.assertEqual(len(matched_nodes), 2)
    self.assertTrue(matched_nodes[0]['IsRoot'])
    self.assertEqual(matched_nodes[1].name, 'Photography')
    self.assertEqual(matched_nodes[1]['Name'],'Photography')
    self.assertEqual(unmatched_dirs, [])

    matched_nodes, ummatched_dirs = self._fs.path_to_node(
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
    self._fs.get('/api/v2/node/zx4Fx')
    testdir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(testdir, 'testdata', 'root_node.json')) as f:
      self.assertEqual(json.loads(self._cmd_output.getvalue()),
                       json.load(f))

  @parameterized.expand([
    ('/Photography/',
     u'San Francisco by helicopter 2014\n'
     u'SmugMug homepage slide show\n'
     u'New Journal style: Big photos!\n'
     u'Samples from my new 200-400\n'
     u'Paris and San Franciso videos by night\n'
     u'Jackson Hole\n'
     u'San Francisco skyline\n'
     u'Giant prints for SmugMug\'s walls\n'
     u'Testing video on the new Canon 7D\n'
     u'Pictures I loved from the week\n'
     u'Baldy\'s first experiments with HDR\n'
     u'Canon 30D versus Fuji S5 image comparisons\n'
     u'Mac color tests\n'
     u'Ofoto, Shutterfly, EZprints compared\n'
     u'Printing services test prints\n'
     u'Quantum Q Flash 5D\n'),

    ('/Photography/San Francisco by helicopter 2014',
     u'DSC_5752.jpg\n'
     u'DSC_5903.jpg\n'
     u'DSC_5932.jpg\n'
     u'DSC_5947.jpg\n'
     u'DSC_5978.jpg\n'
     u'SF by air for 48 inch print-5978.jpg\n'
     u'DSC_6023.jpg\n'
     u'DSC_6069.jpg\n'
     u'DSC_6110.jpg\n'
     u'DSC_5626.jpg\n'
     u'DSC_5657.jpg\n'
     u'Von Wong-2807.jpg\n'
     u'Von Wong-009783.jpg\n'
     u'Von Wong-009789.jpg\n'
     u'Von Wong-009812.jpg\n'
     u'Von Wong-009906.jpg\n'
     u'DSC_4933.jpg\n'
     u'Logan Leia wave pool.jpg\n'),

    ('/Photography/invalid',
     '"invalid" not found in "/Photography".\n'),

    (u'/Photography/inval\xefd',
     u'"inval\xefd" not found in "/Photography".\n')])
  @responses.activate
  def test_ls(self, folder, expected_message):
    self._fs.ls(None, os.path.normpath(folder), False)
    self.assertEqual(
      self._cmd_output.getvalue(),
      os.path.normpath(expected_message))


if __name__ == '__main__':
  unittest.main()

import smugmug
import smugmug_fs
import test_utils

import responses
import unittest

class TestSmugMugFS(unittest.TestCase):

  def setUp(self):
    self._fs = smugmug_fs.SmugMugFS(smugmug.FakeSmugMug())

    test_utils.add_mock_requests(responses)

  @responses.activate
  def test_get_root_node(self):
    self.assertTrue(self._fs.get_root_node('cmac')['IsRoot'])

  @responses.activate
  def test_get_children(self):
    root_node = self._fs.get_root_node('cmac')
    root_children = root_node.get_children()
    self.assertEquals(len(root_children), 17)
    folder_node = root_children[3]
    self.assertEquals(folder_node.name, 'Photography')
    self.assertEquals(folder_node['Name'], 'Photography')

    folder_children = folder_node.get_children()
    self.assertEquals(len(folder_children), 16)
    album_node = folder_children[0]
    self.assertEquals(album_node.name, 'San Francisco by helicopter 2014')
    self.assertEquals(album_node['Name'], 'San Francisco by helicopter 2014')

    album_children = album_node.get_children()
    self.assertEquals(len(album_children), 18)
    file_node = album_children[0]
    self.assertEquals(file_node.name, 'DSC_5752.jpg')
    self.assertEquals(file_node['FileName'], 'DSC_5752.jpg')

  @responses.activate
  def test_get_child(self):
    root_node = self._fs.get_root_node('cmac')
    photography = root_node.get_child('Photography')
    self.assertEquals(photography['Name'], 'Photography')

    invalid_child = root_node.get_child('Missing folder')
    self.assertIsNone(invalid_child)

  @responses.activate
  def test_path_to_node(self):
    matched_nodes, unmatched_dirs = self._fs.path_to_node('cmac', '')
    self.assertEquals(len(matched_nodes), 1)
    self.assertTrue(matched_nodes[0].node['IsRoot'])
    self.assertEquals(unmatched_dirs, [])

    matched_nodes, ummatched_dirs = self._fs.path_to_node('cmac', '/')
    self.assertEquals(len(matched_nodes), 1)
    self.assertTrue(matched_nodes[0].node['IsRoot'])
    self.assertEquals(unmatched_dirs, [])

    matched_nodes, ummatched_dirs = self._fs.path_to_node('cmac', 'Photography')
    self.assertEquals(len(matched_nodes), 2)
    self.assertTrue(matched_nodes[0].node['IsRoot'])
    self.assertEquals(matched_nodes[1].name, 'Photography')
    self.assertEquals(matched_nodes[1].node['Name'],'Photography')
    self.assertEquals(unmatched_dirs, [])

    matched_nodes, ummatched_dirs = self._fs.path_to_node('cmac', '/Photography')
    self.assertEquals(matched_nodes[-1].name, 'Photography')
    self.assertEquals(matched_nodes[-1].node['Name'], 'Photography')
    self.assertEquals(unmatched_dirs, [])

    matched_nodes, unmatched_dirs = self._fs.path_to_node(
        'cmac', '/Photography/San Francisco by helicopter 2014')
    self.assertEquals(len(matched_nodes), 3)
    self.assertTrue(matched_nodes[0].node['IsRoot'])
    self.assertEquals(matched_nodes[1].node['Name'], 'Photography')
    self.assertEquals(matched_nodes[2].node['Name'],
                      'San Francisco by helicopter 2014')
    self.assertEquals(unmatched_dirs, [])

    matched_nodes, unmatched_dirs = self._fs.path_to_node('cmac', '/invalid1')
    self.assertEquals(len(matched_nodes), 1)
    self.assertTrue(matched_nodes[0].node['IsRoot'])
    self.assertEquals(unmatched_dirs, ['invalid1'])

    matched_nodes, unmatched_dirs = self._fs.path_to_node(
      'cmac', '/Photography/invalid2')
    self.assertEquals(len(matched_nodes), 2)
    self.assertTrue(matched_nodes[0].node['IsRoot'])
    self.assertEquals(matched_nodes[1].name, 'Photography')
    self.assertEquals(matched_nodes[1].node['Name'], 'Photography')
    self.assertEquals(unmatched_dirs, ['invalid2'])

if __name__ == '__main__':
  unittest.main()

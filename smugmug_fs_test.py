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
    root_children = list(self._fs.get_children(root_node))
    self.assertEquals(len(root_children), 17)
    folder_name, folder_node = root_children[3]
    self.assertEquals(folder_name, 'Photography')
    self.assertEquals(folder_node['Name'], 'Photography')

    folder_children = list(self._fs.get_children(folder_node))
    self.assertEquals(len(folder_children), 16)
    album_name, album_node = folder_children[0]
    self.assertEquals(album_name, 'San Francisco by helicopter 2014')
    self.assertEquals(album_node['Name'], 'San Francisco by helicopter 2014')

    album_children = list(self._fs.get_children(album_node))
    self.assertEquals(len(album_children), 18)
    file_name, file_node = album_children[0]
    self.assertEquals(file_name, 'DSC_5752.jpg')
    self.assertEquals(file_node['FileName'], 'DSC_5752.jpg')

  @responses.activate
  def test_get_child(self):
    root_node = self._fs.get_root_node('cmac')
    photography = self._fs.get_child(root_node, 'Photography')
    self.assertEquals(photography['Name'], 'Photography')

    invalid_child = self._fs.get_child(root_node, 'Missing folder')
    self.assertIsNone(invalid_child)

  @responses.activate
  def test_path_to_node(self):
    node, matched, unmatched = self._fs.path_to_node('cmac', '')
    self.assertTrue(node['IsRoot'])
    self.assertEquals(matched, [])
    self.assertEquals(unmatched, [])

    node, matched, ummatched = self._fs.path_to_node('cmac', '/')
    self.assertTrue(node['IsRoot'])
    self.assertEquals(matched, [])
    self.assertEquals(unmatched, [])

    node, matched, ummatched = self._fs.path_to_node('cmac', 'Photography')
    self.assertEquals(node['Name'],'Photography')
    self.assertEquals(matched, ['Photography'])
    self.assertEquals(unmatched, [])

    node, matched, ummatched = self._fs.path_to_node('cmac', '/Photography')
    self.assertEquals(node['Name'], 'Photography')
    self.assertEquals(matched, ['Photography'])
    self.assertEquals(unmatched, [])

    node, matched, unmatched = self._fs.path_to_node(
        'cmac', '/Photography/San Francisco by helicopter 2014')
    self.assertEquals(node['Name'], 'San Francisco by helicopter 2014')
    self.assertEquals(matched, ['Photography',
                                'San Francisco by helicopter 2014'])
    self.assertEquals(unmatched, [])

    node, matched, unmatched = self._fs.path_to_node('cmac', '/invalid1')
    self.assertTrue(node['IsRoot'])
    self.assertEquals(matched, [])
    self.assertEquals(unmatched, ['invalid1'])

    node, matched, unmatched = self._fs.path_to_node(
      'cmac', '/Photography/invalid2')
    self.assertEquals(node['Name'], 'Photography')
    self.assertEquals(matched, ['Photography'])
    self.assertEquals(unmatched, ['invalid2'])

if __name__ == '__main__':
  unittest.main()

import smugcli
import smugmug

import json
import StringIO
import sys
import unittest

RESPONSES = {
  '/api/v2!authuser': json.load(open('testdata/authuser.json')),
  '/api/v2/user/cmac': json.load(open('testdata/user.json')),
  '/api/v2/node/zx4Fx': json.load(open('testdata/root_node.json')),
  '/api/v2/node/zx4Fx!children': json.load(open('testdata/root_children.json')),
  '/api/v2/node/n83bK!children': json.load(open('testdata/folder_children.json')),
  '/api/v2/album/DDnhRD': json.load(open('testdata/album.json')),
  '/api/v2/album/DDnhRD!images': json.load(open('testdata/album_images.json')),
}

class TestSmugCLI(unittest.TestCase):

  def setUp(self):
    self._smugmug = smugmug.FakeSmugMug(RESPONSES)

    self._original_stdout = sys.stdout
    self._cmd_output = StringIO.StringIO()
    sys.stdout = self._cmd_output

  def tearDown(self):
    sys.stdout = self._original_stdout

  def test_get(self):
    smugcli.Commands.get(self._smugmug, ['/api/v2/node/zx4Fx'])
    self.assertEqual(json.loads(self._cmd_output.getvalue()),
                     RESPONSES['/api/v2/node/zx4Fx'])

  def test_ls_folder(self):
    smugcli.Commands.ls(self._smugmug, ['/Photography/'])
    self.assertEqual(self._cmd_output.getvalue(),
                     u'San Francisco by helicopter 2014\n'
                     u'SmugMug homepage slide show\n'
                     u'New Journal style: Big photos!\n'
                     u'Samples from my new 200-400\n'
                     u'Paris and San Franciso videos by night\n'
                     u'Jackson Hole\n'
                     u'San Francisco skyline\n'
                     u'Giant prints for SmugMug\'s walls\n'
                     u'Testing video on the new Canon 7D\n'
                     u'Pictures I loved from the week\n')

  def test_ls_album(self):
    smugcli.Commands.ls(self._smugmug,
                  ['/Photography/San Francisco by helicopter 2014'])
    self.assertEqual(self._cmd_output.getvalue(),
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
                     u'Logan Leia wave pool.jpg\n')

if __name__ == '__main__':
  unittest.main()

import smugcli
import smugmug

import json
import mock
import responses
import StringIO
import sys
import unittest
import urlparse

API_ROOT = 'https://api.smugmug.com'

class TestSmugCLI(unittest.TestCase):

  def setUp(self):
    self._smugmug = smugmug.FakeSmugMug()

    self._original_stdout = sys.stdout
    self._cmd_output = StringIO.StringIO()
    sys.stdout = self._cmd_output

  def tearDown(self):
    sys.stdout = self._original_stdout

  def test_get(self):
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/zx4Fx',
               json=json.load(open('testdata/root_node.json')))

      smugcli.Commands.get(self._smugmug, ['/api/v2/node/zx4Fx'])
      self.assertEqual(json.loads(self._cmd_output.getvalue()),
                       json.load(open('testdata/root_node.json')))

  def test_ls_folder(self):
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
      rsps.add(responses.GET, API_ROOT + '/api/v2!authuser',
               json=json.load(open('testdata/authuser.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/user/cmac',
               json=json.load(open('testdata/user.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/zx4Fx',
               json=json.load(open('testdata/root_node.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/zx4Fx!children',
               json=json.load(open('testdata/root_children.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/n83bK!children',
               json=json.load(open('testdata/folder_children.json')))

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
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
      rsps.add(responses.GET, API_ROOT + '/api/v2!authuser',
               json=json.load(open('testdata/authuser.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/user/cmac',
               json=json.load(open('testdata/user.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/zx4Fx',
               json=json.load(open('testdata/root_node.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/zx4Fx!children',
               json=json.load(open('testdata/root_children.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/n83bK!children',
               json=json.load(open('testdata/folder_children.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/album/DDnhRD',
               json=json.load(open('testdata/album.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/album/DDnhRD!images',
               json=json.load(open('testdata/album_images.json')))

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

  def test_ls_invalid_sub_folder(self):
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
      rsps.add(responses.GET, API_ROOT + '/api/v2!authuser',
               json=json.load(open('testdata/authuser.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/user/cmac',
               json=json.load(open('testdata/user.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/zx4Fx',
               json=json.load(open('testdata/root_node.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/zx4Fx!children',
               json=json.load(open('testdata/root_children.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/n83bK!children',
               json=json.load(open('testdata/folder_children.json')))

      smugcli.Commands.ls(self._smugmug, ['/Photography/invalid'])
      self.assertEqual(self._cmd_output.getvalue(),
                       '"invalid" not found in folder "Photography"\n')

  def test_mkdir(self):
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
      rsps.add(responses.GET, API_ROOT + '/api/v2!authuser',
               json=json.load(open('testdata/authuser.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/user/cmac',
               json=json.load(open('testdata/user.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/zx4Fx',
               json=json.load(open('testdata/root_node.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/zx4Fx!children',
               json=json.load(open('testdata/root_children.json')))
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/XWx8t!children',
               json=json.load(open('testdata/smugmug_node_children.json')))

      def post_handler(request):
        self.assertDictEqual(urlparse.parse_qs(request.body),
                             {'Name': ['smugcli-test'],
                              'Privacy': ['Public'],
                              'SortDirection': ['Ascending'],
                              'SortMethod': ['Name'],
                              'Type': ['Folder']})
        return 201, {}, ''

      rsps.add_callback(responses.POST,
                        API_ROOT + '/api/v2/node/XWx8t!children',
                        callback=post_handler)
      rsps.add(responses.GET, API_ROOT + '/api/v2/node/XWx8t!children',
               json=json.load(open('testdata/smugmug_node_children_mkdir.json')))

      smugcli.Commands.mkdir(self._smugmug, ['/SmugMug/smugcli-test'])
      self.assertEqual(self._cmd_output.getvalue(), '')  # No errors printed

if __name__ == '__main__':
  unittest.main()

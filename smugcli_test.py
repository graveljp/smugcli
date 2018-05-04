import smugcli
import smugmug
import smugmug_fs
import test_utils

import json
import mock
from parameterized import parameterized
import responses
import StringIO
import sys
import unittest
import urlparse

API_ROOT = 'https://api.smugmug.com'

class TestSmugCLI(unittest.TestCase):

  def setUp(self):
    self._fs = smugmug_fs.SmugMugFS(smugmug.FakeSmugMug())

    self._original_stdout = sys.stdout
    self._cmd_output = StringIO.StringIO()
    sys.stdout = self._cmd_output

    test_utils.add_mock_requests(responses)

  def tearDown(self):
    sys.stdout = self._original_stdout

  @responses.activate
  def test_get(self):
    smugcli.Commands.get(self._fs, ['/api/v2/node/zx4Fx'])
    self.assertEqual(json.loads(self._cmd_output.getvalue()),
                     json.load(open('testdata/root_node.json')))

  @parameterized.expand([
    (['/Photography/'],
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

    (['/Photography/San Francisco by helicopter 2014'],
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

    (['/Photography/invalid'],
     '"invalid" not found in "/Photography".\n'),

    (['/Photography/inval\xc3\xafd'],
     u'"inval\xefd" not found in "/Photography".\n')])
  @responses.activate
  def test_ls(self, command_line, expected_message):
    smugcli.Commands.ls(self._fs, command_line)
    self.assertEqual(self._cmd_output.getvalue(), expected_message)

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
      rsps.add(
        responses.GET, API_ROOT + '/api/v2/node/XWx8t!children',
        json=json.load(open('testdata/smugmug_node_children_mkdir.json')))

      smugcli.Commands.mkdir(self._fs, ['/SmugMug/smugcli-test'])
      self.assertEqual(self._cmd_output.getvalue(),
                       u'Creating "SmugMug/smugcli-test".\n')

if __name__ == '__main__':
  unittest.main()

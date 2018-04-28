import smugcli

import glob
import json
import os
import re
import responses
import shutil
import StringIO
import subprocess
import sys
import tempfile
import unittest

class EndToEndTest(unittest.TestCase):

  def setUp(self):
    self._test_dir = tempfile.mkdtemp()

    self._original_stdout = sys.stdout
    self._cmd_output = StringIO.StringIO()
    sys.stdout = self._cmd_output

    self._url_re = re.compile(
      r'https://api\.smugmug\.com/api/v2[\!/](?P<path>.*)')
    self._path_replace_re = re.compile(r'[!/?]')

    self._command_index = 0

  @property
  def stdout(self):
    return self._cmd_output.getvalue()

  def tearDown(self):
    shutil.rmtree(self._test_dir)

    sys.stdout = self._original_stdout

  def _url_path(self, request):
    match = self._url_re.match(request.url)
    assert match
    path = match.group('path')
    path = self._path_replace_re.sub('.', path)
    return '%s.%s' % (request.method, path)

  def _get_cache_folder(self, args):
    test_file, test_name = self.id().split('.', 1)
    return os.path.join(
      'testdata', 'request_cache', test_file, test_name,
      '%02d_%s' % (self._command_index, args[0]))

  def _save_requests(self, cache_folder, requests_sent):
    os.makedirs(cache_folder)

    for i, (request, response) in enumerate(requests_sent):
      data = {'method': request.method,
              'url': request.url,
              'json': response}
      data_path = os.path.join(
        cache_folder, '%02d.%s.json' % (i, self._url_path(request)))
      with open(data_path, 'w') as f:
        f.write(json.dumps(
          data, sort_keys=True, indent=2, separators=(',', ': ')))

  def _mock_requests(self, cache_folder, rsps):
    files = glob.glob(os.path.join(cache_folder, '*'))
    for file in files:
      rsps.add(match_querystring=True,
               **json.load(open(file)))

  def _do(self, *args):
    cache_folder = self._get_cache_folder(args)
    request_cached = os.path.exists(cache_folder)
    if request_cached:
      with responses.RequestsMock() as rsps:
        self._mock_requests(cache_folder, rsps)
        smugcli.run(args)
    else:
      requests_sent = []
      smugcli.run(args, requests_sent=requests_sent)
      self._save_requests(cache_folder, requests_sent)

    self._command_index += 1

  def test_ls(self):
    self._do('ls', '__non_existing_folder__')
    self.assertEqual(self.stdout, '"__non_existing_folder__" not found in ""\n')

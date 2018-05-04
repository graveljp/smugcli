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


class CapturingStream(object):

  def __init__(self):
    self._stdout = sys.stdout
    self._string_io = StringIO.StringIO()

  def write(self, *args, **kwargs):
    self._stdout.write(*args, **kwargs)
    self._string_io.write(*args, **kwargs)

  def getvalue(self):
    return self._string_io.getvalue()

  def reset(self):
    self._string_io.close()
    self._string_io = StringIO.StringIO()


class EndToEndTest(unittest.TestCase):

  def setUp(self):
    print '\n-------------------------'
    print 'Running: %s\n' % self.id()
    self._local_dir = tempfile.mkdtemp()
    self._remote_dir = '__smugcli_unit_tests__'

    self._original_stdout = sys.stdout
    self._cmd_output = CapturingStream()
    sys.stdout = self._cmd_output

    self._url_re = re.compile(
      r'https://api\.smugmug\.com/api/v2[\!/](?P<path>.*)')
    self._path_replace_re = re.compile(r'[!/?]')

    self._command_index = 0
    self._pending = set()
    self._replay_cached_requests = os.path.exists(self._get_cache_base_folder())

    self._do('rm -r -f {root}')

  def tearDown(self):
    self._do('rm -r -f {root}')

    if self._pending:
      raise AssertionError(
        'Not all requests have been executed:\n%s' % (
          '\n'.join(sorted(self._pending))))

    shutil.rmtree(self._local_dir)
    sys.stdout = self._original_stdout

  def _url_path(self, request):
    match = self._url_re.match(request.url)
    assert match
    path = match.group('path')
    path = self._path_replace_re.sub('.', path)
    return '%s.%s' % (request.method, path)

  def _get_cache_base_folder(self):
    test_file, test_name = self.id().split('.', 1)
    return os.path.join(
      'testdata', 'request_cache', test_file, test_name)

  def _get_cache_folder(self, args):
    return os.path.join(
      self._get_cache_base_folder(), '%02d_%s' % (self._command_index, args[0]))

  def _save_requests(self, cache_folder, requests_sent):
    os.makedirs(cache_folder)

    for i, (request, response) in enumerate(requests_sent):
      data = {'request': {'method': request.method,
                          'url': request.url,
                          'body': request.body},
              'response': {'status': response.status_code,
                           'json': response.json()}}
      data_path = os.path.join(
        cache_folder, '%02d.%s.json' % (i, self._url_path(request)))
      with open(data_path, 'w') as f:
        f.write(json.dumps(
          data, sort_keys=True, indent=2, separators=(',', ': ')))

  def _mock_requests(self, cache_folder, rsps):
    files = glob.glob(os.path.join(cache_folder, '*'))
    for file in files:
      name = os.sep.join(file.split(os.sep)[-3:])
      self._pending.add(name)
      def callback(req, expected_req, resp, name):
        self.assertIn(name, self._pending)
        self._pending.remove(name)

        self.assertEqual(req.body, expected_req['body'])
        return resp['status'], {}, json.dumps(resp['json'])
      req_resp = json.load(open(file))
      req = req_resp['request']
      resp = req_resp['response']
      rsps.add_callback(
        match_querystring=True,
        method=req['method'],
        url=req['url'],
        callback=lambda x, req=req, resp=resp, name=name: callback(x, req, resp, name))

  def _do(self, command, expected_output=None):
    command = command.format(root=self._remote_dir)
    command = command.replace('/', os.sep)
    print '$ %s' % command
    self._cmd_output.reset()

    args = command.split(' ')
    cache_folder = self._get_cache_folder(args)
    if self._replay_cached_requests:
      with responses.RequestsMock() as rsps:
        self._mock_requests(cache_folder, rsps)
        try:
          smugcli.run(args)
        finally:
          # assert_all_requests_are_fired has to be True duing code execution
          # so that RequestMock could advance in the pending HTTP reques list
          # if many requests have the same URI.
          # assert_all_requests_are_fired has to be False when exiting the
          # context manager because RequestMock.__exit__ otherwise hides all
          # exception emited by the tested code.
          rsps.assert_all_requests_are_fired = False
    else:
      requests_sent = []
      smugcli.run(args, requests_sent=requests_sent)
      self._save_requests(cache_folder, requests_sent)

    self._command_index += 1

    if expected_output is not None:
      expected_output = expected_output.format(root=self._remote_dir)
      expected_output = expected_output.replace('/', os.sep)
      self.assertEqual(self._cmd_output.getvalue(),
                       expected_output)

  def test_ls(self):
    self._do('ls __non_existing_folder__',
             '"__non_existing_folder__" not found in ""\n')

  def test_mkdir(self):
    # Missing parent.
    self._do('mkdir {root}/foo',
             '"{root}" not found in ""\n')

    # Creating root folder.
    self._do('mkdir {root}',
             'Creating "{root}".\n')

    # Cannot create existing folder.
    self._do('mkdir {root}',
             'Path "{root}" already exists.\n')

    # Missing sub-folder parent.
    self._do('mkdir {root}/foo/bar/baz',
             '"foo" not found in "/{root}"\n')

    # Creates all missing parents.
    self._do('mkdir -p {root}/foo/bar/baz',
             'Creating "{root}/foo".\n'
             'Creating "{root}/foo/bar".\n'
             'Creating "{root}/foo/bar/baz".\n')

    # Check that all folders were properly created.
    self._do('ls {root}/foo/bar',
             'baz\n')
    self._do('ls {root}/foo/bar/baz',
             '')  # Folder exists, but is empty.


  def test_rmdir(self):
    # Create a test folder hierarchy.
    self._do('mkdir -p {root}/foo/bar/baz')
    self._do('mkdir -p {root}/buz')

    # Can't remove non-existing folders.
    self._do('rmdir {root}/foo/bar/baz/buz',
             'Folder or album "{root}/foo/bar/baz/buz" not found.\n')

    # Can't remove non-empty folders.
    self._do('rmdir {root}/foo/bar',
             'Cannot delete Folder: "{root}/foo/bar" is not empty\n')

    # Can delete simple folder.
    self._do('rmdir {root}/foo/bar/baz',
             'Deleting {root}/foo/bar/baz\n')
    self._do('ls {root}/foo',
             'bar\n')
    self._do('ls {root}/foo/bar',
             '')  # Folder exists, but is empty.

    # Can delete folder and all it's non-empty parents.
    self._do('rmdir -p {root}/foo/bar',
             'Deleting {root}/foo/bar\n'
             'Deleting {root}/foo\n'
             'Cannot delete Folder: "{root}" is not empty\n')

    self._do('ls {root}/foo',
             '"foo" not found in "/{root}"\n')
    self._do('ls {root}',
             'buz\n')


  def test_rm(self):
    self._do('mkdir -p {root}/foo/bar/baz')
    self._do('mkdir -p {root}/fuz/buz/biz')

    # Not found.
    self._do('rm {root}/does_not_exists',
             '"{root}/does_not_exists" not found.\n')

    # Not empty.
    self._do('rm -f {root}/foo/bar',
             'Folder "{root}/foo/bar" is not empty.\n')

    # Remove leaf.
    self._do('rm -f {root}/foo/bar/baz',
             'Removing "{root}/foo/bar/baz".\n')

    # Doesn't remove non-empty folder by default.
    self._do('rm -f {root}/fuz/buz',
             'Folder "{root}/fuz/buz" is not empty.\n')

    # Can be forced to delete non-empty folders.
    self._do('rm -f -r {root}/fuz/buz',
             'Removing "{root}/fuz/buz".\n')

    self._do('rm -r -f {root}/foo {root}/fuz',
             'Removing "{root}/foo".\n'
             'Removing "{root}/fuz".\n')

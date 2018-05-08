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


REMOTE_DIR = '__smugcli_unit_tests__'


def format_path(path):
  try:
    path = path.format(root=REMOTE_DIR)
  except ValueError:  # Ignore unmatched '{'.
    pass

  path = os.path.normpath(path)
  return path


class ExpectBase(object):
  # Base class for all expected response string matchers.

  def __ne__(self, other):
    return not self.__eq__(other)


class Expect(ExpectBase):

  def __init__(self, string):
    self._string = format_path(string)

  def __eq__(self, other):
    return other == self._string

  def __repr__(self):
    return repr(self._string)


class ExpectPrefix(ExpectBase):

  def __init__(self, prefix):
    self._prefix = format_path(prefix)

  def __eq__(self, other):
    return other.startswith(self._prefix)

  def __repr__(self):
    return repr(self._prefix + '[...]')


class Reply(object):

  def __init__(self, string):
    self._string = string

  def __str__(self):
    return str(self._string)

  def __repr__(self):
    return 'Reply(%s)' % repr(self._string)


class ExpectedInputOutput(object):

  def __init__(self):
    self._expected_io = None

  def set_expected_io(self, expected_io):
    self._expected_io = [Expect(io) if isinstance(io, basestring) else io
                         for io in expected_io] if expected_io else None

  def assert_no_pending(self):
    if self._expected_io:
      raise AssertionError('Pending IO expectation never fulfulled:\n%s' % str(self._expected_io))
    self._expected_io = None

  def write(self, string):
    sys.__stdout__.write(string)

    if self._expected_io is None:
      return

    if string == '\n':
      return

    if not self._expected_io:
      raise AssertionError('Not expecting any more IOs but got: %s' %
                           repr(string))

    io = self._expected_io.pop(0)
    if not isinstance(io, ExpectBase):
      raise AssertionError('Not expecting output message but got: %s' %
                           repr(string))

    if io != string:
      raise AssertionError('Unexpected output: %s != %s' % (repr(string),
                                                            repr(io)))

  def readline(self):
    if not self._expected_io:
      raise AssertionError('Not expecting any more IOs.')

    io = self._expected_io.pop(0)
    if not isinstance(io, Reply):
      raise AssertionError('Not expecting input request.')

    reply = format_path(str(io)) + '\n'
    sys.__stdout__.write(reply)
    return reply


class EndToEndTest(unittest.TestCase):

  def setUp(self):
    print '\n-------------------------'
    print 'Running: %s\n' % self.id()

    cache_folder = self._get_cache_base_folder()
    if bool(os.environ.get('RESET_CACHE')):
      shutil.rmtree(cache_folder)

    self._local_dir = tempfile.mkdtemp()

    self._io = ExpectedInputOutput()
    sys.stdin = self._io
    sys.stdout = self._io

    self._url_re = re.compile(
      r'https://api\.smugmug\.com/api/v2[\!/](?P<path>.*)')
    self._path_replace_re = re.compile(r'[!/?]')

    self._command_index = 0
    self._pending = set()
    self._replay_cached_requests = os.path.exists(cache_folder)

    self._do('rm -r -f {root}')

  def tearDown(self):
    self._io.set_expected_io(None)
    self._do('rm -r -f {root}')

    if self._pending:
      raise AssertionError(
        'Not all requests have been executed:\n%s' % (
          '\n'.join(sorted(self._pending))))

    shutil.rmtree(self._local_dir)
    sys.stdin = sys.__stdin__
    sys.stdout = sys.__stdout__

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

  def _do(self, command, expected_io=None):
    command = format_path(command)
    print '$ %s' % command
    self._io.set_expected_io(expected_io)

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
    self._io.assert_no_pending()

  def test_ls(self):
    self._do('ls __non_existing_folder__',
             ['"__non_existing_folder__" not found in "".'])

  def test_mkdir(self):
    # Missing parent.
    self._do('mkdir {root}/foo',
             ['"{root}" not found in "".'])

    # Creating root folder.
    self._do('mkdir {root}',
             ['Creating "{root}".'])

    # Cannot create existing folder.
    self._do('mkdir {root}',
             ['Path "{root}" already exists.'])

    # Missing sub-folder parent.
    self._do('mkdir {root}/foo/bar/baz',
             ['"foo" not found in "/{root}".'])

    # Creates all missing parents.
    self._do('mkdir -p {root}/foo/bar/baz',
             ['Creating "{root}/foo".',
              'Creating "{root}/foo/bar".',
              'Creating "{root}/foo/bar/baz".'])

    # Check that all folders were properly created.
    self._do('ls {root}/foo/bar',
             ['baz'])
    self._do('ls {root}/foo/bar/baz',
             [])  # Folder exists, but is empty.

    # Can create many folders in one command.
    self._do('mkdir {root}/buz {root}/biz',
             ['Creating "{root}/buz".',
              'Creating "{root}/biz".'])

    self._do('mkdir {root}/baz/biz {root}/buz {root}/baz',
             ['"baz" not found in "/{root}".',
              'Path "{root}/buz" already exists.',
              'Creating "{root}/baz".'])

    self._do('ls {root}',
             ['baz',
              'biz',
              'buz',
              'foo'])

  def test_rmdir(self):
    # Create a test folder hierarchy.
    self._do('mkdir -p {root}/foo/bar/baz')
    self._do('mkdir -p {root}/buz')

    # Can't remove non-existing folders.
    self._do('rmdir {root}/foo/bar/baz/buz',
             ['Folder or album "{root}/foo/bar/baz/buz" not found.'])

    # Can't remove non-empty folders.
    self._do('rmdir {root}/foo/bar',
             ['Cannot delete Folder: "{root}/foo/bar" is not empty.'])

    # Can delete simple folder.
    self._do('rmdir {root}/foo/bar/baz',
             ['Deleting "{root}/foo/bar/baz".'])
    self._do('ls {root}/foo',
             ['bar'])
    self._do('ls {root}/foo/bar',
             [])  # Folder exists, but is empty.

    # Can delete folder and all it's non-empty parents.
    self._do('rmdir -p {root}/foo/bar',
             ['Deleting "{root}/foo/bar".',
              'Deleting "{root}/foo".',
              'Cannot delete Folder: "{root}" is not empty.'])

    self._do('ls {root}/foo',
             ['"foo" not found in "/{root}".'])
    self._do('ls {root}',
             ['buz'])

  def test_rm(self):
    self._do('mkdir -p {root}/foo/bar/baz')
    self._do('mkdir -p {root}/fuz/buz/biz')

    # Not found.
    self._do('rm {root}/does_not_exists',
             ['"{root}/does_not_exists" not found.'])

    # Not empty.
    self._do('rm -f {root}/foo/bar',
             ['Folder "{root}/foo/bar" is not empty.'])

    # Remove leaf.
    self._do('rm -f {root}/foo/bar/baz',
             ['Removing "{root}/foo/bar/baz".'])

    # Doesn't remove non-empty folder by default.
    self._do('rm -f {root}/fuz/buz',
             ['Folder "{root}/fuz/buz" is not empty.'])

    # Can be forced to delete non-empty folders.
    self._do('rm -f -r {root}/fuz/buz',
             ['Removing "{root}/fuz/buz".'])

    # Can remove multiple nodes.
    # Ask for confirmation by default.
    self._do('rm -r {root}/foo {root}/fuz',
             ['Remove Folder node "{root}/foo"? ',
              Reply('n'),
              'Remove Folder node "{root}/fuz"? ',
              Reply('y'),
              'Removing "{root}/fuz".'])
    self._do('rm -r {root}/foo {root}/fuz {root}',
             ['Remove Folder node "{root}/foo"? ',
              Reply('yes'),
              'Removing "{root}/foo".',
              '"{root}/fuz" not found.',
              'Remove Folder node "{root}"? ',
              Reply('YES'),
              'Removing "{root}".'])

if __name__ == '__main__':
  unittest.main()

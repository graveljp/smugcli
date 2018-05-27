import smugcli

import contextlib
import difflib
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

@contextlib.contextmanager
def set_cwd(new_dir):
  original_dir = os.getcwd()
  try:
    os.chdir(new_dir)
    yield
  finally:
    os.chdir(original_dir)

ROOT_DIR = '__smugcli_unit_tests__'


def format_path(path):
  try:
    path = path.format(root=ROOT_DIR)
  except ValueError:  # Ignore unmatched '{'.
    pass

  # On windows, replace '/' for '\\', but keep '\\/' and '/'.
  fix_slash_re = re.compile(r'([^\\])/')
  path = fix_slash_re.sub(r'\1\%s' % os.sep, path)
  path = path.replace('\\/', '/')
  return path


class ExpectBase(object):
  # Base class for all expected response string matchers.

  def __ne__(self, other):
    return not self.__eq__(other)


class Expect(ExpectBase):

  def __init__(self, string):
    self._string = format_path(string)

  def __eq__(self, other):
    return other.strip() == self._string.strip()

  def __str__(self):
    return str(self._string)

  def __repr__(self):
    return repr(self._string)


class ExpectPrefix(ExpectBase):

  def __init__(self, prefix):
    self._prefix = format_path(prefix)

  def __eq__(self, other):
    return other.strip().startswith(self._prefix.strip())

  def __str__(self):
    return str(self._prefix)

  def __repr__(self):
    return 'ExpectPrefix(' + repr(self._prefix) + ')'


class ExpectRegex(ExpectBase):

  def __init__(self, regex):
    self._regex = regex

  def __eq__(self, other):
    return re.match(self._regex, other, re.DOTALL | re.MULTILINE)

  def __repr__(self):
    return 'ExpectRegex(' + repr(self._regex) + ')'


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
    self._cmd_output = StringIO.StringIO()

  def set_expected_io(self, expected_io):
    self._expected_io = (
      [Expect(io) if isinstance(io, basestring) else io for io in expected_io]
      if expected_io is not None else None)
    self._cmd_output = StringIO.StringIO()

  def assert_no_pending(self):
    self._CheckExpectedOutput()

    if self._expected_io:
      raise AssertionError('Pending IO expectation never fulfulled:\n%s' % str(self._expected_io))
    self.set_expected_io(None)

  def write(self, string):
    sys.__stdout__.write(string)
    self._cmd_output.write(string)

  def readline(self):
    self._CheckExpectedOutput()

    if not self._expected_io:
      raise AssertionError('Not expecting any more IOs.')

    io = self._expected_io.pop(0)
    if not isinstance(io, Reply):
      raise AssertionError('Not expecting input request.')

    reply = format_path(str(io)) + '\n'
    sys.__stdout__.write(reply)
    return reply

  def _CheckExpectedOutput(self):
    output = self._cmd_output.getvalue()
    self._cmd_output = StringIO.StringIO()

    if not output or self._expected_io is None:
      return

    if not self._expected_io:
      raise AssertionError('Not expecting any more IOs but got: %s' %
                           repr(output))

    io = self._expected_io.pop(0)
    if not isinstance(io, ExpectBase):
      raise AssertionError('Not expecting output message but got: %s' %
                           repr(output))

    if io != output:
      raise AssertionError('Unexpected output:\n'
                           '%s' % ''.join(difflib.ndiff(
                             str(io).splitlines(True),
                             str(output).splitlines(True))))


class EndToEndTest(unittest.TestCase):

  def setUp(self):
    print '\n-------------------------'
    print 'Running: %s\n' % self.id()

    cache_folder = self._get_cache_base_folder()
    if bool(os.environ.get('RESET_CACHE')):
      shutil.rmtree(cache_folder, ignore_errors=True)

    self._io = ExpectedInputOutput()
    sys.stdin = self._io
    sys.stdout = self._io

    self._api_url_re = re.compile(
      r'https://api\.smugmug\.com/api/v2[\!/](?P<path>.*)')
    self._upload_url_re = re.compile(
      r'https://(?P<path>upload)\.smugmug\.com/')
    self._path_replace_re = re.compile(r'[!/?]')

    self._command_index = 0
    self._pending = set()
    self._replay_cached_requests = os.path.exists(cache_folder)

    self._do('rm -r -f {root}')
    shutil.rmtree(ROOT_DIR, ignore_errors=True)

  def tearDown(self):
    self._io.set_expected_io(None)
    self._do('rm -r -f {root}')
    shutil.rmtree(ROOT_DIR, ignore_errors=True)

    if self._pending:
      raise AssertionError(
        'Not all requests have been executed:\n%s' % (
          '\n'.join(sorted(self._pending))))

    sys.stdin = sys.__stdin__
    sys.stdout = sys.__stdout__

  def _url_path(self, request):
    match = (self._api_url_re.match(request.url) or
             self._upload_url_re.match(request.url))
    assert match
    path = match.group('path')
    path = self._path_replace_re.sub('.', path)
    return '%s.%s' % (request.method, path)

  def _get_cache_base_folder(self):
    test_file, test_name = self.id().split('.', 1)
    return os.path.join(
      os.path.dirname(os.path.realpath(__file__)),
      'testdata', 'request_cache', test_file, test_name)

  def _get_cache_folder(self, args):
    return os.path.join(
      self._get_cache_base_folder(), '%02d_%s' % (self._command_index, args[0]))

  def _encode_body(self, body):
    if body:
      try:
        body.encode('UTF-8')
      except:
        return body.encode('base64')

    return body

  def _save_requests(self, cache_folder, requests_sent):
    os.makedirs(cache_folder)

    for i, (request, response) in enumerate(requests_sent):

      data = {'request': {'method': request.method,
                          'url': request.url,
                          'body': self._encode_body(request.body)},
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
        self.assertEqual(self._encode_body(req.body), expected_req['body'])
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

  def _stage_files(self, dest, files):
    dest_path = format_path(dest)
    try:
      os.makedirs(dest_path)
    except OSError:
      pass
    for f in files:
      if isinstance(f, basestring):
        shutil.copy(format_path(f), dest_path)
      else:
        shutil.copyfile(format_path(f[0]), os.path.join(dest_path, f[1]))

  def test_get(self):
    self._do('get \\/api\\/v2\\/user',
             [ExpectPrefix('{\n  "Code": 200,\n  "Message": "Ok"')])

  def test_ls(self):
    # Fails if node doesn't exists.
    self._do('ls {root}',
             ['"{root}" not found in "".'])
    self._do('ls {root}/foo',
             ['"{root}" not found in "".'])

    # Works if node exists:
    self._do('mkdir -p {root}/foo/bar {root}/foo/baz')
    self._do('ls {root}',
             ['foo'])
    self._do('ls {root}/foo',
             ['bar\n'
              'baz'])

    # Shows full node JSON info in -l mode:
    self._do('ls -l {root}',
             [ExpectRegex(r'{\n  .*  "Name": "foo"')])

    # Lists other user's folder
    self._do('ls -u cmac',
             [ExpectRegex(r'.*^Photography$')])

  def test_mkdir(self):
    # Missing parent.
    self._do('mkdir {root}/foo',
             ['"{root}" not found in "".'])

    # Creating root folder.
    self._do('mkdir {root}',
             ['Creating Folder "{root}".'])

    # Cannot create existing folder.
    self._do('mkdir {root}',
             ['Path "{root}" already exists.'])

    # Missing sub-folder parent.
    self._do('mkdir {root}/foo/bar/baz',
             ['"foo" not found in "/{root}".'])

    # Creates all missing parents.
    self._do('mkdir -p {root}/foo/bar/baz',
             ['Creating Folder "{root}/foo".\n'
              'Creating Folder "{root}/foo/bar".\n'
              'Creating Folder "{root}/foo/bar/baz".'])

    # Check that all folders were properly created.
    self._do('ls {root}/foo/bar',
             ['baz'])
    self._do('ls {root}/foo/bar/baz',
             [])  # Folder exists, but is empty.

    # Can create many folders in one command.
    self._do('mkdir {root}/buz {root}/biz',
             ['Creating Folder "{root}/buz".\n'
              'Creating Folder "{root}/biz".'])

    self._do('mkdir {root}/baz/biz {root}/buz {root}/baz',
             ['"baz" not found in "/{root}".\n'
              'Path "{root}/buz" already exists.\n'
              'Creating Folder "{root}/baz".'])

    self._do('ls {root}',
             ['baz\n'
              'biz\n'
              'buz\n'
              'foo'])

  def test_mkalbum(self):
    # Missing parent.
    self._do('mkalbum {root}/folder/album',
             ['"{root}" not found in "".'])

    # Create all missing folders.
    self._do('mkalbum -p {root}/folder/album',
             ['Creating Folder "{root}".\n'
              'Creating Folder "{root}/folder".\n'
              'Creating Album "{root}/folder/album".'])

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
             ['Deleting "{root}/foo/bar".\n'
              'Deleting "{root}/foo".\n'
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
              'Removing "{root}/foo".\n'
              '"{root}/fuz" not found.\n'
              'Remove Folder node "{root}"? ',
              Reply('YES'),
              'Removing "{root}".'])

  def test_upload(self):
    # Can't upload to non-existing album.
    self._do('upload testdata/SmugCLI_1.jpg {root}/folder/album',
             ['Album not found: "{root}/folder/album".'])

    # Can't upload to folders.
    self._do('mkdir -p {root}/folder')
    self._do('upload testdata/SmugCLI_1.jpg {root}/folder',
             ['Cannot upload images in node of type "Folder".'])

    # Can upload to album.
    self._do('mkalbum -p {root}/folder/album')
    self._do('upload testdata/SmugCLI_1.jpg {root}/folder/album',
             ['Uploading "testdata/SmugCLI_1.jpg" to "{root}/folder/album"...'])

    # Can't upload duplicate.
    self._do('upload testdata/SmugCLI_1.jpg {root}/folder/album',
             ['Skipping "testdata/SmugCLI_1.jpg", file already exists in Album '
              '"{root}/folder/album".'])

    # Can upload multiple files
    self._do('upload testdata/Sm?gCLI_1.* testdata/SmugCLI_2.jpg {root}/folder/album',
             ['Uploading "testdata/SmugCLI_1.gif" to "{root}/folder/album"...\n'
              'Skipping "testdata/SmugCLI_1.jpg", file already exists in Album '
              '"{root}/folder/album".\n'
              'Uploading "testdata/SmugCLI_1.png" to "{root}/folder/album"...\n'
              'Uploading "testdata/SmugCLI_2.jpg" to "{root}/folder/album"...'])

  def test_sync(self):
    self._stage_files('{root}/dir', ['testdata/SmugCLI_1.jpg',
                                     'testdata/SmugCLI_2.jpg',
                                     'testdata/SmugCLI_3.jpg'])
    self._stage_files('{root}/dir/album', ['testdata/SmugCLI_4.jpg',
                                           'testdata/SmugCLI_5.jpg'])
    self._do('sync {root}',
             ['Syncing local folders "{root}" to SmugMug folder "/".\n'
              'Creating Folder "{root}".\n'
              'Creating Folder "{root}/dir".\n'
              'Creating Album "{root}/dir/Images from folder dir".\n'
              'Uploading "{root}/dir/SmugCLI_1.jpg".\n'
              'Uploading "{root}/dir/SmugCLI_2.jpg".\n'
              'Uploading "{root}/dir/SmugCLI_3.jpg".\n'
              'Creating Album "{root}/dir/album".\n'
              'Uploading "{root}/dir/album/SmugCLI_4.jpg".\n'
              'Uploading "{root}/dir/album/SmugCLI_5.jpg".\n'])

    self._do(
      'sync {root}',
      ['Syncing local folders "{root}" to SmugMug folder "/".\n'
       'Found matching remote album "{root}/dir/Images from folder dir".\n'
       'Found matching remote album "{root}/dir/album".\n'])

    with set_cwd(format_path('{root}')):
      self._do(
        'sync -t {root} dir',
        ['Syncing local folders "dir" to SmugMug folder "/__smugcli_tests__".\n'
         'Found matching remote album "{root}/dir/Images from folder dir".\n'
         'Found matching remote album "{root}/dir/album".\n'])

    self._stage_files('{root}/dir',
                      [('testdata/SmugCLI_5.jpg', 'SmugCLI_2.jpg')])
    self._stage_files('{root}/dir/album',
                      [('testdata/SmugCLI_2.jpg', 'SmugCLI_5.jpg')])
    self._do(
      'sync {root}',
      ['Syncing local folders "{root}" to SmugMug folder "/".\n'
       'Found matching remote album "{root}/dir/Images from folder dir".\n'
       'File "{root}/dir/SmugCLI_2.jpg" exists, but has changed.'
       ' Deleting old version.\n'
       'Re-uploading "{root}/dir/SmugCLI_2.jpg".\n'
       'Found matching remote album "{root}/dir/album".\n'
       'File "{root}/dir/album/SmugCLI_5.jpg" exists, but has changed.'
       ' Deleting old version.\n'
       'Re-uploading "{root}/dir/album/SmugCLI_5.jpg".\n'])

  def test_mkdir_folder_depth_limits(self):
    # Can't create more than 5 folder deep.
    self._do('mkdir -p {root}/1/2/3/4',
             ['Creating Folder "{root}".\n'
              'Creating Folder "{root}/1".\n'
              'Creating Folder "{root}/1/2".\n'
              'Creating Folder "{root}/1/2/3".\n'
              'Creating Folder "{root}/1/2/3/4".\n'])
    self._do('mkdir -p {root}/1/2/3/4/5',
             ['Cannot create "{root}/1/2/3/4/5", SmugMug does not support '
              'folder more than 5 level deep.'])
    self._do('mkalbum -p {root}/1/2/3/4/5',
             ['Creating Album "{root}/1/2/3/4/5".'])

  def test_sync_folder_depth_limits(self):
    self._stage_files('{root}/1/2/3/4/album', ['testdata/SmugCLI_1.jpg'])
    self._do('sync {root}',
             ['Syncing local folders "{root}" to SmugMug folder "/".\n'
              'Creating Folder "__smugcli_tests__".\n'
              'Creating Folder "__smugcli_tests__/1".\n'
              'Creating Folder "__smugcli_tests__/1/2".\n'
              'Creating Folder "__smugcli_tests__/1/2/3".\n'
              'Creating Folder "__smugcli_tests__/1/2/3/4".\n'
              'Creating Album "__smugcli_tests__/1/2/3/4/album".\n'
              'Uploading "__smugcli_tests__/1/2/3/4/album/SmugCLI_1.jpg".\n'])

    with set_cwd(format_path('{root}/1')):
      self._do('sync 2 -t {root}/1',
               ['Syncing local folders "2" to SmugMug folder "/{root}/1".\n'
                'Found matching remote album "{root}/1/2/3/4/album".'])

    self._stage_files('{root}/1/2/3/4/5/album', ['testdata/SmugCLI_1.jpg'])
    self._do('sync {root}',
             ['Syncing local folders "{root}" to SmugMug folder "/".\n'
              'Cannot create "{root}/1/2/3/4/5/album", SmugMug does not'
              ' support folder more than 5 level deep.'])

    with set_cwd(format_path('{root}/1')):
      self._do('sync 2 -t {root}/1',
               ['Syncing local folders "2" to SmugMug folder "/{root}/1".\n'
                'Cannot create "{root}/1/2/3/4/5/album", SmugMug does not'
                ' support folder more than 5 level deep.'])

if __name__ == '__main__':
  unittest.main()

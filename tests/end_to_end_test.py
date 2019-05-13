from smugcli import smugcli

import io_expectation as expect

import base64
import contextlib
import glob
import json
import os
import re
import responses
import shutil
import six
import sys
import unittest

CONFIG_FILE = os.path.expanduser('~/.smugcli')
TEST_DIR = os.path.dirname(os.path.realpath(__file__))

@contextlib.contextmanager
def set_cwd(new_dir):
  original_dir = os.getcwd()
  try:
    os.chdir(new_dir)
    yield
  finally:
    os.chdir(original_dir)

ROOT_DIR = '__smugcli_tests__'


def format_path(path):
  try:
    path = path.format(root=ROOT_DIR,
                       testdata=os.path.join(TEST_DIR, 'testdata'))
  except ValueError:  # Ignore unmatched '{'.
    pass

  # On windows, replace '/' for '\\', keeping '\\/' as '/'.
  fix_slash_re = re.compile(r'([^\\])/')
  path = fix_slash_re.sub(r'\1\%s' % os.sep, path)
  path = path.replace('\\/', '/')
  return path


class EndToEndTest(unittest.TestCase):

  def setUp(self):
    print('\n-------------------------')
    print('Running: %s\n' % self.id())

    # The response library cannot replay requests in a multi-threaded
    # environment. We have to disable threading for testing...
    with open(CONFIG_FILE) as f:
      self._config = json.load(f)
    self._config.update({
      'folder_threads': 1,
      'file_threads': 1,
      'upload_threads': 1,
    })

    cache_folder = self._get_cache_base_folder()
    if bool(os.environ.get('RESET_CACHE')):
      shutil.rmtree(cache_folder, ignore_errors=True)

    self._io = expect.ExpectedInputOutput()
    self._io.set_transform_fn(format_path)
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

    sys.stdin = self._io._original_stdin
    sys.stdout = self._io._original_stdout

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
      TEST_DIR, 'testdata', 'request_cache', test_file, test_name)

  def _get_cache_folder(self, args):
    return os.path.join(
      self._get_cache_base_folder(), '%02d_%s' % (self._command_index, args[0]))

  def _encode_body(self, body):
    if body:
      if hasattr(body, 'read'):
        pos = body.tell()
        body.seek(0)
        data = body.read()
        body.seek(pos)
      else:
        data = body

      if isinstance(data, six.binary_type):
        try:
          return data.decode('UTF-8')
        except:
          return base64.b64encode(data).decode('utf-8')
      return data

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
      with open(file) as f:
        req_resp = json.load(f)
      req = req_resp['request']
      resp = req_resp['response']
      rsps.add_callback(
        match_querystring=True,
        method=req['method'],
        url=req['url'],
        callback=lambda x, req=req, resp=resp, name=name: callback(x, req, resp, name))

  def _do(self, command, expected_io=None):
    command = format_path(command)
    print('$ %s' % command)
    self._io.set_expected_io(expected_io)

    args = command.split(' ')
    cache_folder = self._get_cache_folder(args)
    if self._replay_cached_requests:
      with responses.RequestsMock() as rsps:
        self._mock_requests(cache_folder, rsps)
        try:
          smugcli.run(args, self._config)
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
      smugcli.run(args, self._config, requests_sent=requests_sent)
      self._save_requests(cache_folder, requests_sent)

    self._command_index += 1
    self._io.assert_expectations_fulfilled()

  def _stage_files(self, dest, files):
    dest_path = format_path(dest)
    try:
      os.makedirs(dest_path)
    except OSError:
      pass
    for f in files:
      if isinstance(f, six.string_types):
        shutil.copy(format_path(f), dest_path)
      else:
        shutil.copyfile(format_path(f[0]), os.path.join(dest_path, f[1]))

  def test_get(self):
    self._do('get \\/api\\/v2\\/user',
             expect.Somewhere(
               ['"Code": 200,',
                '"Message": "Ok",']))

  def test_ls(self):
    # Fails if node doesn't exists.
    self._do('ls {root}',
             '"{root}" not found in "".')
    self._do('ls {root}/foo',
             '"{root}" not found in "".')

    # Works if node exists:
    self._do('mkdir -p {root}/foo/bar {root}/foo/baz')
    self._do('ls {root}',
             'foo')
    self._do('ls {root}/foo',
             ['bar',
              'baz'])

    # Shows full node JSON info in -l mode:
    self._do('ls -l {root}',
             expect.Somewhere('"Name": "foo",'))

    # Lists other user's folder
    self._do('ls -u cmac',
             expect.Somewhere('Photography'))

  def test_mkdir(self):
    # Missing parent.
    self._do('mkdir {root}/foo',
             '"{root}" not found in "".')

    # Creating root folder.
    self._do('mkdir {root}',
             'Creating Folder "{root}".')

    # Cannot create existing folder.
    self._do('mkdir {root}',
             'Path "{root}" already exists.')

    # Missing sub-folder parent.
    self._do('mkdir {root}/foo/bar/baz',
             '"foo" not found in "/{root}".')

    # Creates all missing parents.
    self._do('mkdir -p {root}/foo/bar/baz',
             ['Creating Folder "{root}/foo".',
              'Creating Folder "{root}/foo/bar".',
              'Creating Folder "{root}/foo/bar/baz".'])

    # Check that all folders were properly created.
    self._do('ls {root}/foo/bar',
             'baz')
    self._do('ls {root}/foo/bar/baz',
             [])  # Folder exists, but is empty.

    # Can create many folders in one command.
    self._do('mkdir {root}/buz {root}/biz',
             ['Creating Folder "{root}/buz".',
              'Creating Folder "{root}/biz".'])

    self._do('mkdir {root}/baz/biz {root}/buz {root}/baz',
             ['"baz" not found in "/{root}".',
              'Path "{root}/buz" already exists.',
              'Creating Folder "{root}/baz".'])

    self._do('ls {root}',
             ['baz',
              'biz',
              'buz',
              'foo'])

  def test_mkdir_privacy(self):
    self._do('mkdir -p {root}/default/folder')
    self._do('ls -l {root}/default',
             expect.Somewhere('"Privacy": "Public",'))

    self._do('mkdir -p {root}/public/folder --privacy=public')
    self._do('ls -l {root}/public',
             expect.Somewhere('"Privacy": "Public",'))

    self._do('mkdir -p {root}/unlisted/folder --privacy=unlisted')
    self._do('ls -l {root}/unlisted',
             expect.Somewhere('"Privacy": "Unlisted",'))

    self._do('mkdir -p {root}/private/folder --privacy=private')
    self._do('ls -l {root}/private',
             expect.Somewhere('"Privacy": "Private",'))

  def test_mkdir_folder_depth_limits(self):
    # Can't create more than 5 folder deep.
    self._do('mkdir -p {root}/1/2/3/4',
             ['Creating Folder "{root}".',
              'Creating Folder "{root}/1".',
              'Creating Folder "{root}/1/2".',
              'Creating Folder "{root}/1/2/3".',
              'Creating Folder "{root}/1/2/3/4".'])
    self._do('mkdir -p {root}/1/2/3/4/5',
             ['Cannot create "{root}/1/2/3/4/5", SmugMug does not support '
              'folder more than 5 level deep.'])
    self._do('mkalbum -p {root}/1/2/3/4/5',
             ['Creating Album "{root}/1/2/3/4/5".'])

  def test_mkalbum(self):
    # Missing parent.
    self._do('mkalbum {root}/folder/album',
             ['"{root}" not found in "".'])

    # Create all missing folders.
    self._do('mkalbum -p {root}/folder/album',
             ['Creating Folder "{root}".',
              'Creating Folder "{root}/folder".',
              'Creating Album "{root}/folder/album".'])

  def test_mkalbum_privacy(self):
    self._do('mkalbum -p {root}/default/album')
    self._do('ls -l {root}/default',
             expect.Somewhere('"Privacy": "Public",'))

    self._do('mkalbum -p {root}/public/album --privacy=public')
    self._do('ls -l {root}/public',
             expect.Somewhere('"Privacy": "Public",'))

    self._do('mkalbum -p {root}/unlisted/album --privacy=unlisted')
    self._do('ls -l {root}/unlisted',
             expect.Somewhere('"Privacy": "Unlisted",'))

    self._do('mkalbum -p {root}/private/album --privacy=private')
    self._do('ls -l {root}/private',
             expect.Somewhere('"Privacy": "Private",'))

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
              expect.Reply('n'),
              'Remove Folder node "{root}/fuz"? ',
              expect.Reply('y'),
              'Removing "{root}/fuz".'])
    self._do('rm -r {root}/foo {root}/fuz {root}',
             ['Remove Folder node "{root}/foo"? ',
              expect.Reply('yes'),
              'Removing "{root}/foo".',
              '"{root}/fuz" not found.',
              'Remove Folder node "{root}"? ',
              expect.Reply('YES'),
              'Removing "{root}".'])

  def test_upload(self):
    # Can't upload to non-existing album.
    self._do('upload {testdata}/SmugCLI_1.jpg {root}/folder/album',
             ['Album not found: "{root}/folder/album".'])

    # Can't upload to folders.
    self._do('mkdir -p {root}/folder')
    self._do('upload {testdata}/SmugCLI_1.jpg {root}/folder',
             ['Cannot upload images in node of type "Folder".'])

    # Can upload to album.
    self._do('mkalbum -p {root}/folder/album')
    self._do(
      'upload {testdata}/SmugCLI_1.jpg {root}/folder/album',
      ['Uploading "{testdata}/SmugCLI_1.jpg" to "{root}/folder/album"...'])

    # Can't upload duplicate.
    self._do(
      'upload {testdata}/SmugCLI_1.jpg {root}/folder/album',
      ['Skipping "{testdata}/SmugCLI_1.jpg", file already exists in Album '
       '"{root}/folder/album".'])

    # Can upload multiple files
    self._do(
      'upload {testdata}/Sm?gCLI_1.* {testdata}/SmugCLI_2.jpg '
      '{root}/folder/album',
      ['Uploading "{testdata}/SmugCLI_1.gif" to "{root}/folder/album"...',
       'Skipping "{testdata}/SmugCLI_1.jpg", file already exists in Album '
       '"{root}/folder/album".',
       'Uploading "{testdata}/SmugCLI_1.png" to "{root}/folder/album"...',
       'Uploading "{testdata}/SmugCLI_2.jpg" to "{root}/folder/album"...'])

  def test_sync(self):
    self._stage_files('{root}/dir', ['{testdata}/SmugCLI_1.jpg',
                                     '{testdata}/SmugCLI_2.jpg',
                                     '{testdata}/SmugCLI_3.jpg'])
    self._stage_files('{root}/dir/album', ['{testdata}/SmugCLI_4.jpg',
                                           '{testdata}/SmugCLI_5.jpg'])
    self._do('sync {root} /',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Creating Folder "{root}".',
                'Creating Folder "{root}/dir".',
                'Creating Album "{root}/dir/Images from folder dir".',
                'Creating Album "{root}/dir/album".',
                'Uploaded "{root}/dir/SmugCLI_1.jpg".',
                'Uploaded "{root}/dir/SmugCLI_2.jpg".',
                'Uploaded "{root}/dir/SmugCLI_3.jpg".',
                'Uploaded "{root}/dir/album/SmugCLI_4.jpg".',
                'Uploaded "{root}/dir/album/SmugCLI_5.jpg".')])

    self._do(
      'sync {root} /',
      ['Syncing "{root}" to SmugMug folder "/".',
       'Proceed (yes\\/no)?',
       expect.Reply('yes'),
       expect.AnyOrder(
         expect.Anything().repeatedly(),
         'Found matching remote album "{root}/dir/Images from folder dir".',
         'Found matching remote album "{root}/dir/album".')])

    with set_cwd(format_path('{root}')):
      self._do(
        'sync dir {root}',
        ['Syncing "dir" to SmugMug folder "/{root}".',
         'Proceed (yes\\/no)?',
         expect.Reply('yes'),
         expect.AnyOrder(
           expect.Anything().repeatedly(),
           'Found matching remote album "{root}/dir/Images from folder dir".',
           'Found matching remote album "{root}/dir/album".')])

    self._stage_files('{root}/dir',
                      [('{testdata}/SmugCLI_5.jpg', 'SmugCLI_2.jpg')])
    self._stage_files('{root}/dir/album',
                      [('{testdata}/SmugCLI_2.jpg', 'SmugCLI_5.jpg')])
    self._do(
      'sync {root} /',
      ['Syncing "{root}" to SmugMug folder "/".',
       'Proceed (yes\\/no)?',
       expect.Reply('yes'),
       expect.AnyOrder(
         expect.Anything().repeatedly(),
         'Found matching remote album "{root}/dir/Images from folder dir".',
         'File "{root}/dir/SmugCLI_2.jpg" exists, but has changed.'
         ' Deleting old version.',
         'Re-uploaded "{root}/dir/SmugCLI_2.jpg".',
         'Found matching remote album "{root}/dir/album".',
         'File "{root}/dir/album/SmugCLI_5.jpg" exists, but has changed.'
         ' Deleting old version.',
         'Re-uploaded "{root}/dir/album/SmugCLI_5.jpg".')])

  def test_sync_privacy(self):
    self._stage_files('{root}/default/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root}',
             expect.Somewhere(expect.Reply('yes')))
    self._do('ls -l {root}/default',
             expect.Somewhere('"Privacy": "Public",'))

    self._stage_files('{root}/public/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root} --privacy=public',
             expect.Somewhere(expect.Reply('yes')))
    self._do('ls -l {root}/public',
             expect.Somewhere('"Privacy": "Public",'))

    self._stage_files('{root}/unlisted/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root} --privacy=unlisted',
             expect.Somewhere(expect.Reply('yes')))
    self._do('ls -l {root}/unlisted',
             expect.Somewhere('"Privacy": "Unlisted",'))

    self._stage_files('{root}/private/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root} --privacy=private',
             expect.Somewhere(expect.Reply('yes')))
    self._do('ls -l {root}/private',
             expect.Somewhere('"Privacy": "Private",'))

  def test_sync_folder_depth_limits(self):
    self._stage_files('{root}/1/2/3/4/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do(
      'sync {root}',
      ['Syncing "{root}" to SmugMug folder "/".',
       'Proceed (yes\\/no)?',
       expect.Reply('yes'),
       expect.AnyOrder(
         expect.Anything().repeatedly(),
         'Creating Folder "{root}".',
         'Creating Folder "{root}/1".',
         'Creating Folder "{root}/1/2".',
         'Creating Folder "{root}/1/2/3".',
         'Creating Folder "{root}/1/2/3/4".',
         'Creating Album "{root}/1/2/3/4/album".',
         'Uploaded "{root}/1/2/3/4/album/SmugCLI_1.jpg".')])

    with set_cwd(format_path('{root}/1')):
      self._do('sync 2 {root}/1',
               ['Syncing "2" to SmugMug folder "/{root}/1".',
                'Proceed (yes\\/no)?',
                expect.Reply('yes'),
                expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/1/2/3/4/album".')])

    self._stage_files('{root}/1/2/3/4/5/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Cannot create "{root}/1/2/3/4/5/album", SmugMug does not'
                ' support folder more than 5 level deep.')])

    with set_cwd(format_path('{root}/1')):
      self._do('sync 2 {root}/1',
               ['Syncing "2" to SmugMug folder "/{root}/1".',
                'Proceed (yes\\/no)?',
                expect.Reply('yes'),
                expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Cannot create "{root}/1/2/3/4/5/album", SmugMug does not'
                  ' support folder more than 5 level deep.')])

  def test_sync_whitespace(self):
    if os.name == 'nt':
      folder = '{root}/ folder/ album'
      filename = ' file . jpg'
    else:
      folder = '{root}/ folder / album '
      filename = ' file . jpg '

    self._stage_files(folder, [('{testdata}/SmugCLI_1.jpg', filename)])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Creating Folder "{root}".',
                'Creating Folder "{root}/folder".',
                'Creating Album "{root}/folder/album".',
                'Uploaded "%s/%s".' % (folder, filename))])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Found matching remote album "{root}/folder/album".')])

  def test_sync_confirmation(self):
    self._stage_files('{root}/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)? ',
              expect.Reply('yes'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Creating Folder "{root}".',
                'Creating Album "{root}/album".',
                'Uploaded "{root}/album/SmugCLI_1.jpg".')])

    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)? ',
              expect.Reply('y'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Found matching remote album "{root}/album".')])

    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)? ',
              expect.Reply('no')])

    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)? ',
              expect.Reply('n')])

  def test_sync_force(self):
    self._stage_files('{root}/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync -f {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Creating Folder "{root}".',
                'Creating Album "{root}/album".',
                'Uploaded "{root}/album/SmugCLI_1.jpg".')])

    self._do('sync --force {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Found matching remote album "{root}/album".')])

  def test_sync_sub_folders(self):
    self._stage_files('{root}/local/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('mkdir -p {root}/Pics')
    self._do('sync {root}/local/album {root}/Pics',
             ['Syncing "{root}/local/album" to SmugMug folder "/{root}/Pics".',
              'Proceed (yes\\/no)? ',
              expect.Reply('y'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Creating Album "{root}/Pics/album".',
                'Uploaded "{root}/local/album/SmugCLI_1.jpg".')])

    self._do('sync {root}/local/album/ {root}/Pics/album',
             ['Syncing "{root}/local/album/" to SmugMug album '
              '"/{root}/Pics/album".',
              'Proceed (yes\\/no)? ',
              expect.Reply('y'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Found matching remote album "{root}/Pics/album".')])

  def test_sync_invalid_src(self):
    self._stage_files('{root}/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('mkalbum -p {root}')

    self._do('sync {root}/file {root}/folder/ {root}/dir/* {root}',
             ['Files not found:',
              '{root}/file',
              '{root}/folder/',
              '{root}/dir/*'])

    self._do('sync {root}/file {root}/album/ {root}/dir/* {root}',
             ['Files not found:',
              '{root}/file',
              '{root}/dir/*'])

    self._do('sync {root}/file {root}',
             ['File not found:',
              '{root}/file'])

    self._do('sync {root}/album/* {root}',
             ['Syncing "{root}/album/SmugCLI_1.jpg" to SmugMug album '
              '"/{root}".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

  def test_sync_folder(self):
    self._stage_files('{root}/src/album1', ['{testdata}/SmugCLI_1.jpg',
                                            '{testdata}/SmugCLI_2.jpg'])
    self._stage_files('{root}/src/album2', ['{testdata}/SmugCLI_3.jpg'])
    self._do('mkdir -p {root}/dst')

    self._do('sync {root}/src/ {root}/dst',
             ['Syncing "{root}/src/" to SmugMug folder "/{root}/dst"',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Creating Album "{root}/dst/album1".',
                'Uploaded "{root}/src/album1/SmugCLI_1.jpg".',
                'Uploaded "{root}/src/album1/SmugCLI_2.jpg".',
                'Creating Album "{root}/dst/album2".',
                'Uploaded "{root}/src/album2/SmugCLI_3.jpg".')])

  def test_sync_multiple_files(self):
    self._stage_files('{root}/dir1', ['{testdata}/SmugCLI_1.jpg'])
    self._stage_files('{root}/dir2', ['{testdata}/SmugCLI_1.jpg',
                                      '{testdata}/SmugCLI_2.jpg',
                                      '{testdata}/SmugCLI_3.jpg'])
    self._stage_files('{root}/dir3', ['{testdata}/SmugCLI_1.jpg'])
    self._do('mkalbum -p {root}/album')

    self._do('sync {root}/dir1/*.jpg {root}/dir2/* {root}/dir3/ {root}/album',
             ['Syncing:',
              '  {root}/dir1/SmugCLI_1.jpg',
              '  {root}/dir2/SmugCLI_1.jpg',
              '  {root}/dir2/SmugCLI_2.jpg',
              '  {root}/dir2/SmugCLI_3.jpg',
              '  {root}/dir3/',
              'to SmugMug album "/{root}/album"',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Found matching remote album "{root}/album".',
                'Uploaded "{root}/dir1/SmugCLI_1.jpg".',
                'Uploaded "{root}/dir2/SmugCLI_1.jpg".',
                'Uploaded "{root}/dir2/SmugCLI_2.jpg".',
                'Uploaded "{root}/dir2/SmugCLI_3.jpg".',
                'Uploaded "{root}/dir3/SmugCLI_1.jpg".',
                'Sync complete.')])

  def test_sync_multiple_folders(self):
    self._stage_files('{root}/album1', ['{testdata}/SmugCLI_1.jpg'])
    self._stage_files('{root}/dir2/album2', ['{testdata}/SmugCLI_2.jpg'])
    self._stage_files('{root}/dir3/subdir3/album3',
                      ['{testdata}/SmugCLI_3.jpg'])
    self._do('mkdir -p {root}/folder')

    self._do('sync {root}/album1 {root}/dir2/* {root}/dir3/ {root}/folder',
             ['Syncing:',
              '  {root}/album1',
              '  {root}/dir2/album2',
              '  {root}/dir3/',
              'to SmugMug folder "/{root}/folder"',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Creating Album "{root}/folder/album1".',
                'Creating Album "{root}/folder/album2".',
                'Creating Folder "{root}/folder/subdir3".',
                'Creating Album "{root}/folder/subdir3/album3".',
                'Uploaded "{root}/album1/SmugCLI_1.jpg".',
                'Uploaded "{root}/dir2/album2/SmugCLI_2.jpg".',
                'Uploaded "{root}/dir3/subdir3/album3/SmugCLI_3.jpg".',
                'Sync complete.')])

  def test_sync_paths_to_album(self):
    self._stage_files('{root}/dir1', ['{testdata}/SmugCLI_1.jpg',
                                      '{testdata}/SmugCLI_2.jpg'])
    self._do('mkalbum -p {root}/album')
    self._do('sync {root}/dir1/* {root}/album',
             ['Syncing:',
              '  {root}/dir1/SmugCLI_1.jpg',
              '  {root}/dir1/SmugCLI_2.jpg',
              'to SmugMug album "/{root}/album".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                expect.Anything().repeatedly(),
                'Found matching remote album "{root}/album".',
                'Uploaded "{root}/dir1/SmugCLI_1.jpg".',
                'Uploaded "{root}/dir1/SmugCLI_2.jpg".')])

  def test_sync_files_to_album(self):
    self._stage_files('{root}/dir1', ['{testdata}/SmugCLI_1.jpg',
                                      '{testdata}/SmugCLI_2.jpg'])
    self._do('mkalbum -p {root}/album')
    with set_cwd(format_path('{root}/dir1')):
      self._do('sync * {root}/album',
               ['Syncing:',
                '  SmugCLI_1.jpg',
                '  SmugCLI_2.jpg',
                'to SmugMug album "/{root}/album".',
                'Proceed (yes\\/no)?',
                expect.Reply('yes'),
                expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/album".',
                  'Uploaded "./SmugCLI_1.jpg".',
                  'Uploaded "./SmugCLI_2.jpg".')])

  def test_sync_files_to_folder(self):
    self._stage_files('{root}', ['{testdata}/SmugCLI_1.jpg',
                                 '{testdata}/SmugCLI_2.jpg'])
    self._do('mkdir -p {root}/folder')
    self._do('sync {root}/* {root}/folder',
             'Can\'t upload files to folder. Please sync to an album node.')

  def test_sync_folders_to_album(self):
    self._stage_files('{root}/dir1', ['{testdata}/SmugCLI_1.jpg'])
    self._stage_files('{root}/dir2', ['{testdata}/SmugCLI_2.jpg'])
    self._do('mkalbum -p {root}/album')
    self._do('sync {root}/* {root}/album',
             'Can\'t upload folders to an album. Please sync to a folder node.')

  def test_sync_default_arguments(self):
    self._stage_files('{root}', ['{testdata}/SmugCLI_1.jpg',
                                 '{testdata}/SmugCLI_2.jpg',
                                 '{testdata}/SmugCLI_3.jpg'])
    self._do('mkalbum -p {root}')
    self._do('sync',
             ['Syncing "." to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

    self._do('sync {root}/ {root}',
             ['Syncing "{root}/" to SmugMug album "/{root}".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

    self._do('sync {root}/SmugCLI_1.jpg {root}/SmugCLI_2.jpg {root}',
             ['Syncing:',
              '  {root}/SmugCLI_1.jpg',
              '  {root}/SmugCLI_2.jpg',
              'to SmugMug album "/{root}".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

  def test_sync_deprecated_target_argument(self):
    self._do('sync -t dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positinal argument.'])

    self._do('sync --target=dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positinal argument.'])

    self._do('sync a -t dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positinal argument.'])

    self._do('sync a --target=dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positinal argument.'])

    self._do('sync a b -t dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positinal argument.'])

    self._do('sync a b --target=dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positinal argument.'])


if __name__ == '__main__':
  unittest.main()

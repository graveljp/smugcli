"""Base class for tests running against the real SmugMug service."""
from typing import List, Sequence, Tuple

import base64
import contextlib
import glob
import json
import locale
import os
import re
import shutil
import sys
import unittest
from urllib.parse import urlsplit

import requests
import responses

import io_expectation as expect

from smugcli import smugcli_commands


CONFIG_FILE = os.path.expanduser('~/.smugcli')
TEST_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = '__smugcli_tests__'


class IntegrationTestBase(unittest.TestCase):
  """Integration test invoking SmugCLI against the real SmugMug service."""

  def setUp(self):
    print('\n-------------------------')
    print(f'Running: {self.id()}\n')

    # The response library cannot replay requests in a multi-threaded
    # environment. We have to disable threading for testing...
    with open(CONFIG_FILE, encoding=locale.getpreferredencoding()) as file:
      self._config = json.load(file)
    self._config.update({
      'folder_threads': 1,
      'file_threads': 1,
      'upload_threads': 1,
    })

    cache_folder = self._get_cache_base_folder()
    reuse_responses = os.environ.get('REUSE_RESPONSES')
    if (reuse_responses is None or
        reuse_responses.lower() not in ('true', 't', 'yes', 'y', 1)):
      shutil.rmtree(cache_folder, ignore_errors=True)

    self._io = expect.ExpectedInputOutput()
    self._io.set_transform_fn(self._format_path)
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

    self._io.close()

  @contextlib.contextmanager
  def _set_cwd(self, new_dir: str):
    """Change the current working directory of the Python interpreter."""
    original_dir = os.getcwd()
    try:
      os.chdir(new_dir)
      yield
    finally:
      os.chdir(original_dir)

  def _format_path(self, path: str) -> str:
    """Format path for the current file system."""
    try:
      path = path.format(root=ROOT_DIR,
                         testdata=os.path.join(TEST_DIR, 'testdata'))
    except ValueError:  # Ignore unmatched '{'.
      pass

    # On windows, replace '/' for '\\', keeping '\\/' as '/'.
    fix_slash_re = re.compile(r'([^\\])/')
    path = fix_slash_re.sub(rf'\1\{os.sep}', path)
    path = path.replace('\\/', '/')
    return path

  def _url_path(self, request):
    match = (self._api_url_re.match(request.url) or
             self._upload_url_re.match(request.url))
    assert match
    path = match.group('path')
    path = self._path_replace_re.sub('.', path)
    return f'{request.method}.{path}'

  def _get_cache_base_folder(self):
    test_file, test_name = self.id().split('.', 1)
    return os.path.join(
      TEST_DIR, 'testdata', 'request_cache', test_file, test_name)

  def _get_cache_folder(self, args: Sequence[str]):
    return os.path.join(
      self._get_cache_base_folder(), f'{self._command_index:02d}_{args[0]}')

  def _encode_body(self, body):
    if body:
      if hasattr(body, 'read'):
        pos = body.tell()
        body.seek(0)
        data = body.read()
        body.seek(pos)
      else:
        data = body

      if isinstance(data, bytes):
        try:
          return data.decode('UTF-8')
        except UnicodeError:
          return base64.b64encode(data).decode('utf-8')
      return data

    return body

  def _save_requests(
      self,
      cache_folder: str,
      requests_sent: List[Tuple[requests.PreparedRequest, requests.Response]]
  ) -> None:
    os.makedirs(cache_folder)

    for i, (request, response) in enumerate(requests_sent):
      data = {'request': {'method': request.method,
                          'url': request.url,
                          'body': self._encode_body(request.body)},
              'response': {'status': response.status_code,
                           'text': response.text}}
      data_path = os.path.join(
        cache_folder, f'{i:02d}.{self._url_path(request)}.json')
      with open(data_path, 'w',
                encoding=locale.getpreferredencoding()) as file:
        file.write(json.dumps(
          data, sort_keys=True, indent=2, separators=(',', ': ')))

  def _mock_requests(self,
                     cache_folder: str,
                     rsps: responses.RequestsMock) -> None:
    files = glob.glob(os.path.join(cache_folder, '*'))
    def callback(req, expected_req, resp, name):
      self.assertIn(name, self._pending)
      self._pending.remove(name)
      self.assertEqual(self._encode_body(req.body), expected_req['body'])
      return resp['status'], {}, resp['text']
    for file in files:
      name = os.sep.join(file.split(os.sep)[-3:])
      self._pending.add(name)
      with open(file, encoding=locale.getpreferredencoding()) as file:
        req_resp = json.load(file)
      req = req_resp['request']
      resp = req_resp['response']
      rsps.add_callback(
        match=[responses.matchers.query_string_matcher(
          urlsplit(req['url']).query)],
        method=req['method'],
        url=req['url'],
        callback=lambda x, req=req, res=resp, n=name: callback(x, req, res, n))

  def _do(self, command: str, expected_io=None):
    command = self._format_path(command)
    print(f'$ {command}')
    self._io.set_expected_io(expected_io)

    args = command.split(' ')
    cache_folder = self._get_cache_folder(args)
    if self._replay_cached_requests:
      with responses.RequestsMock() as rsps:
        self._mock_requests(cache_folder, rsps)
        try:
          smugcli_commands.run(args, self._config)
        finally:
          # assert_all_requests_are_fired has to be True during code execution
          # so that RequestMock could advance in the pending HTTP request list
          # if many requests have the same URI.
          # assert_all_requests_are_fired has to be False when exiting the
          # context manager because RequestMock.__exit__ otherwise hides all
          # exception emitted by the tested code.
          rsps.assert_all_requests_are_fired = False
    else:
      requests_sent = []  # type: List[Tuple[requests.PreparedRequest, requests.Response]]  # pylint: disable=line-too-long
      smugcli_commands.run(args, self._config, requests_sent=requests_sent)
      self._save_requests(cache_folder, requests_sent)

    self._command_index += 1
    self._io.assert_expectations_fulfilled()

  def _stage_files(self, dest, files):
    dest_path = self._format_path(dest)
    try:
      os.makedirs(dest_path)
    except OSError:
      pass
    for file in files:
      if isinstance(file, str):
        shutil.copy(self._format_path(file), dest_path)
      else:
        shutil.copyfile(self._format_path(file[0]),
                        os.path.join(dest_path, file[1]))

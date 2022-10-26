"""Utils shared by many unit tests."""

import json
import locale
import os
from urllib.parse import urlsplit

API_ROOT = 'https://api.smugmug.com'

def add_mock_requests(responses):
  """Add mock HTTP requests for tests to use."""
  testdir = os.path.dirname(os.path.realpath(__file__))

  with open(os.path.join(testdir, 'testdata', 'authuser.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2!authuser'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])
  with open(os.path.join(testdir, 'testdata', 'user.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2/user/cmac'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])
  with open(os.path.join(testdir, 'testdata', 'root_node.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2/node/zx4Fx'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])
  with open(os.path.join(testdir, 'testdata', 'root_children.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2/node/zx4Fx!children?count=10&start=1'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])
  with open(os.path.join(testdir, 'testdata', 'root_children_page2.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2/node/zx4Fx!children?count=10&start=11'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])
  with open(os.path.join(testdir, 'testdata', 'folder_children.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2/node/n83bK!children?count=10&start=1'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])
  with open(os.path.join(testdir, 'testdata', 'folder_children_page2.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2/node/n83bK!children?count=10&start=11'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])
  with open(os.path.join(testdir, 'testdata', 'album.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2/album/DDnhRD'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])
  with open(os.path.join(testdir, 'testdata', 'album_images.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2/album/DDnhRD!images?count=10&start=1'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])
  with open(os.path.join(testdir, 'testdata', 'album_images_page2.json'),
            encoding=locale.getpreferredencoding()) as handle:
    url = API_ROOT + '/api/v2/album/DDnhRD!images?count=10&start=11'
    responses.add(
        responses.GET, url,
        json=json.load(handle),
        match=[responses.matchers.query_string_matcher(
          urlsplit(url).query)])

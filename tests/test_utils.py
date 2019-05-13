import json
import os

API_ROOT = 'https://api.smugmug.com'

def add_mock_requests(responses):
  testdir = os.path.dirname(os.path.realpath(__file__))

  with open(os.path.join(testdir, 'testdata', 'authuser.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2!authuser',
        json=json.load(f),
        match_querystring=True)
  with open(os.path.join(testdir, 'testdata', 'user.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2/user/cmac',
        json=json.load(f),
        match_querystring=True)
  with open(os.path.join(testdir, 'testdata', 'root_node.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2/node/zx4Fx',
        json=json.load(f),
        match_querystring=True)
  with open(os.path.join(testdir, 'testdata', 'root_children.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2/node/zx4Fx!children?count=10&start=1',
        json=json.load(f),
        match_querystring=True)
  with open(os.path.join(testdir, 'testdata', 'root_children_page2.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2/node/zx4Fx!children?count=10&start=11',
        json=json.load(f),
        match_querystring=True)
  with open(os.path.join(testdir, 'testdata', 'folder_children.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2/node/n83bK!children?count=10&start=1',
        json=json.load(f),
        match_querystring=True)
  with open(os.path.join(testdir, 'testdata', 'folder_children_page2.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2/node/n83bK!children?count=10&start=11',
        json=json.load(f),
        match_querystring=True)
  with open(os.path.join(testdir, 'testdata', 'album.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2/album/DDnhRD',
        json=json.load(f),
        match_querystring=True)
  with open(os.path.join(testdir, 'testdata', 'album_images.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2/album/DDnhRD!images?count=10&start=1',
        json=json.load(f),
        match_querystring=True)
  with open(os.path.join(testdir, 'testdata', 'album_images_page2.json')) as f:
    responses.add(
        responses.GET, API_ROOT + '/api/v2/album/DDnhRD!images?count=10&start=11',
        json=json.load(f),
        match_querystring=True)

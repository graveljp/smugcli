import json

API_ROOT = 'https://api.smugmug.com'

def add_mock_requests(responses):
  responses.add(
      responses.GET, API_ROOT + '/api/v2!authuser',
      json=json.load(open('testdata/authuser.json')),
      match_querystring=True)
  responses.add(
      responses.GET, API_ROOT + '/api/v2/user/cmac',
      json=json.load(open('testdata/user.json')),
      match_querystring=True)
  responses.add(
      responses.GET, API_ROOT + '/api/v2/node/zx4Fx',
      json=json.load(open('testdata/root_node.json')),
      match_querystring=True)
  responses.add(
      responses.GET, API_ROOT + '/api/v2/node/zx4Fx!children?count=10&start=1',
      json=json.load(open('testdata/root_children.json')),
      match_querystring=True)
  responses.add(
      responses.GET, API_ROOT + '/api/v2/node/zx4Fx!children?count=10&start=11',
      json=json.load(open('testdata/root_children_page2.json')),
      match_querystring=True)
  responses.add(
      responses.GET, API_ROOT + '/api/v2/node/n83bK!children?count=10&start=1',
      json=json.load(open('testdata/folder_children.json')),
      match_querystring=True)
  responses.add(
      responses.GET, API_ROOT + '/api/v2/node/n83bK!children?count=10&start=11',
      json=json.load(open('testdata/folder_children_page2.json')),
      match_querystring=True)
  responses.add(
      responses.GET, API_ROOT + '/api/v2/album/DDnhRD',
      json=json.load(open('testdata/album.json')),
      match_querystring=True)
  responses.add(
      responses.GET, API_ROOT + '/api/v2/album/DDnhRD!images?count=10&start=1',
      json=json.load(open('testdata/album_images.json')),
      match_querystring=True)
  responses.add(
      responses.GET, API_ROOT + '/api/v2/album/DDnhRD!images?count=10&start=11',
      json=json.load(open('testdata/album_images_page2.json')),
      match_querystring=True)

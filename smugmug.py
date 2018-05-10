# Main interface to the SmugMug web service.

import base64
import json
import math
import md5
import re
import requests
import smugmug_oauth
import smugmug_fs

API_ROOT = 'https://api.smugmug.com'
API_UPLOAD = 'https://upload.smugmug.com/'
API_REQUEST = 'https://api.smugmug.com/api/developer/apply'

PAGE_START_RE = re.compile(r'(\?.*start=)[0-9]+')

class Error(Exception):
  """Base class for all exception of this module."""


class NotLoggedInError(Error):
  """Error raised if the user is not logged in."""


class UnexpectedResponseError(Error):
  """Error raised when encountering unexpected data returned by SmugMug."""


class NodeList(object):
  def __init__(self, smugmug, json):
    self._smugmug = smugmug

    response = json['Response']
    locator = response['Locator']
    page_info = response['Pages']
    self._page_size = page_info['Count']
    self._total_size = page_info['Total']
    num_pages = int(math.ceil(float(self._total_size) / self._page_size)
                    if self._page_size else 0)
    self._pages = [None] * num_pages
    if num_pages:
      self._pages[0] = response[locator]
    self._uri = PAGE_START_RE.sub(r'\1%d', response['Uri'])

  def __len__(self):
    return self._total_size

  def __getitem__(self, item):
    if item < 0 or item >= self._total_size:
      raise IndexError

    page_index = item / self._page_size
    if self._pages[page_index] is None:
      new_page_uri = self._uri % (page_index * self._page_size + 1)
      json = self._smugmug.get_json(new_page_uri)
      response = json['Response']
      locator = response['Locator']
      self._pages[page_index] = response[locator]
    return Node(self._smugmug,
                self._pages[page_index][item - page_index * self._page_size])


class Node(object):
  def __init__(self, smugmug, json):
    self._smugmug = smugmug
    self._json = json

  @property
  def json(self):
    return self._json

  @property
  def name(self):
    return self._json.get('FileName') or self._json['Name']

  def get(self, url_name, **kwargs):
    uri = self.uri(url_name)
    return self._smugmug.get(uri, **kwargs)

  def post(self, uri_name, data=None, json=None, **kwargs):
    uri = self.uri(uri_name)
    return self._smugmug.post(uri, data, json, **kwargs)

  def patch(self, uri_name, data=None, json=None, **kwargs):
    uri = self.uri(uri_name)
    return self._smugmug.patch(uri, data, json, **kwargs)

  def delete(self, **kwargs):
    uri = self._json.get('Uri')
    return self._smugmug.delete(uri, **kwargs)

  def upload(self, uri_name, filename, data, headers=None):
    uri = self.uri(uri_name)
    return self._smugmug.upload(uri, filename, data, headers)

  def uri(self, url_name):
    uri = self._json.get('Uris', {}).get(url_name, {}).get('Uri')
    if not uri:
      raise UnexpectedResponseError('Node does not have a "%s" uri.' % url_name)
    return uri

  def __getitem__(self, key):
    return self._json[key]

  def __contains__(self, key):
    return key in self._json

  def __eq__(self, other):
    return self._json == other

  def __ne__(self, other):
    return self._json != other

  def get_children(self, params=None):
    if 'Type' not in self._json:
      raise UnexpectedResponseError('Node does not have a "Type" attribute.')

    params = params or {}
    params = {
      'start': params.get('start', 1),
      'count': params.get('count', self._smugmug.config.get('page_size', 1000))}

    if self._json['Type'] == 'Album':
      return self.get('Album').get('AlbumImages', params=params)
    else:
      return self.get('ChildNodes', params=params)

  def get_child(self, child_name):
    for child in self.get_children():
      if child.name == child_name:
        return child
    return None


def Wrapper(smugmug, json):
  response = json['Response']
  if 'Pages' in response:
    return NodeList(smugmug, json)
  else:
    locator = response['Locator']
    endpoint = response[locator]
    return Node(smugmug, endpoint)


class SmugMug(object):
  def __init__(self, config, requests_sent=None):
    self._config = config
    self._smugmug_oauth = None
    self._oauth = None
    self._fs = smugmug_fs.SmugMugFS(self)
    self._session = requests.Session()
    self._requests_sent = requests_sent

  @property
  def config(self):
    return self._config

  @property
  def service(self):
    if not self._smugmug_oauth:
      if 'api_key' in self.config:
        self._smugmug_oauth = smugmug_oauth.SmugMugOAuth(self.config['api_key'])
      else:
        print 'No API key provided.'
        print 'Please request an API key at %s' % API_REQUEST
        print 'and run "smugcli.py login"'
        raise NotLoggedInError
    return self._smugmug_oauth

  @property
  def oauth(self):
    if not self._oauth:
      if self.service and 'access_token' in self.config:
        self._oauth = self.service.get_oauth(self.config['access_token'])
      else:
        print 'User not logged in. Please run the "login" command'
        raise NotLoggedInError
    return self._oauth

  def login(self, api_key):
    self.config['api_key'] = api_key
    self.config['access_token'] = self.service.request_access_token()

  def logout(self):
    if 'api_key' in self.config:
      del self.config['api_key']
    if 'access_token' in self.config:
      del self.config['access_token']
    self._service = None
    self._session = None

  def get_auth_user(self):
    return self.get('/api/v2!authuser')['NickName']

  def get_json(self, path, **kwargs):
    req = requests.Request('GET', API_ROOT + path,
                           headers={'Accept': 'application/json'},
                           auth=self.oauth,
                           **kwargs).prepare()
    resp = self._session.send(req)
    if self._requests_sent is not None:
      self._requests_sent.append((req, resp))
    resp.raise_for_status()
    return resp.json()

  def get(self, path, **kwargs):
    reply = self.get_json(path, **kwargs)
    return Wrapper(self, reply)

  def post(self, path, data=None, json=None, **kwargs):
    req = requests.Request('POST',
                           API_ROOT + path,
                           data=data,
                           json=json,
                           headers={'Accept': 'application/json'},
                           auth=self.oauth,
                           **kwargs).prepare()
    resp = self._session.send(req)
    if self._requests_sent is not None:
      self._requests_sent.append((req, resp))
    return resp

  def patch(self, path, data=None, json=None, **kwargs):
    return requests.patch(API_ROOT + path,
                          data=data, json=json,
                          headers={'Accept': 'application/json'},
                          auth=self.oauth,
                          **kwargs)

  def delete(self, path, data=None, json=None, **kwargs):
    req = requests.Request('DELETE',
                           API_ROOT + path,
                           auth=self.oauth,
                           headers={'Accept': 'application/json'},
                           **kwargs).prepare()
    resp = self._session.send(req)
    if self._requests_sent is not None:
      self._requests_sent.append((req, resp))
    return resp

  def upload(self, uri, filename, data, additional_headers=None):
    headers = {'Content-Length': str(len(data)),
               'Content-MD5': base64.b64encode(md5.new(data).digest()),
               'X-Smug-AlbumUri': uri,
               'X-Smug-FileName': filename,
               'X-Smug-ResponseType': 'JSON',
               'X-Smug-Version': 'v2'}
    headers.update(additional_headers or {})
    return requests.post(API_UPLOAD, data=data, headers=headers,
                         auth=self.oauth)


class FakeSmugMug(SmugMug):
  def __init__(self, config=None):
    config = config or {}
    config['page_size'] = 10
    super(FakeSmugMug, self).__init__(config or {})

  @property
  def service(self):
    return None

  @property
  def oauth(self):
    return None

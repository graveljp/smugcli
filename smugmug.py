# Main interface to the SmugMug web service.

import base64
import json
import md5
import requests
import smugmug_oauth
import smugmug_fs

API_ROOT = 'https://api.smugmug.com'
API_UPLOAD = 'https://upload.smugmug.com/'
API_REQUEST = 'https://api.smugmug.com/api/developer/apply'

class Error(Exception):
  """Base class for all exception of this module."""


class NotLoggedInError(Error):
  """Error raised if the user is not logged in."""


class PageIterator:
  def __init__(self, smugmug, json):
    self._smugmug = smugmug
    self._global_index = 0
    self._set_page(json)

  def _set_page(self, json):
    response = json['Response']
    locator = response['Locator']
    self._pages = response.get('Pages', {})
    self._page_content = response.get(locator, [])
    self._page_index = 0

  def __len__(self):
    return self._page.get('Total')

  def __next__(self):
    return next()

  def next(self):
    if self._global_index >= self._pages.get('Total'):
      raise StopIteration

    if self._global_index >= self._pages['Start'] + self._pages['Count'] - 1:
      self._set_page(self._smugmug.get_json(self._pages['NextPage']))

    result = self._page_content[self._page_index]
    self._global_index += 1
    self._page_index += 1

    return Node(self._smugmug, result)


class NodeList(object):
  def __init__(self, smugmug, json):
    self._smugmug = smugmug
    self._json = json

  def __iter__(self):
    return PageIterator(self._smugmug, self._json)

  def __len__(self):
    return self._json['Response'].get('Pages', {}).get('Total')


class Node(object):
  def __init__(self, smugmug, json):
    self._smugmug = smugmug
    self._json = json

  @property
  def json(self):
    return self._json

  def get(self, url_name, **kwargs):
    uri = self.uri(url_name)
    return self._smugmug.get(uri, **kwargs) if uri else None

  def post(self, uri_name, data=None, json=None, **kwargs):
    uri = self.uri(uri_name)
    if not uri:
      return None
    return self._smugmug.post(uri, data, json, **kwargs)

  def patch(self, uri_name, data=None, json=None, **kwargs):
    uri = self.uri(uri_name)
    return self._smugmug.patch(uri, data, json, **kwargs)

  def upload(self, uri_name, filename, data, headers=None):
    uri = self.uri(uri_name)
    return self._smugmug.upload(uri, filename, data, headers)

  def uri(self, url_name):
    return self._json.get('Uris', {}).get(url_name, {}).get('Uri')

  def __getitem__(self, key):
    return self._json[key]

  def __contains__(self, key):
    return key in self._json

  def __eq__(self, other):
    return self._json == other

  def __ne__(self, other):
    return self._json != other


def Wrapper(smugmug, json):
  response = json['Response']
  if 'Pages' in response:
    return NodeList(smugmug, json)
  else:
    locator = response['Locator']
    endpoint = response[locator]
    return Node(smugmug, endpoint)


class SmugMug(object):
  def __init__(self, config):
    self._config = config
    self._smugmug_oauth = None
    self._oauth = None
    self._fs = smugmug_fs.SmugMugFS(self)

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
    return requests.get(API_ROOT + path,
                        headers={'Accept': 'application/json'},
                        auth=self.oauth,
                        **kwargs).json()

  def get(self, path, **kwargs):
    reply = self.get_json(path, **kwargs)
    return Wrapper(self, reply)

  def post(self, path, data=None, json=None, **kwargs):
    return requests.post(API_ROOT + path,
                         data=data, json=json,
                         headers={'Accept': 'application/json'},
                         auth=self.oauth,
                         **kwargs)

  def patch(self, path, data=None, json=None, **kwargs):
    return requests.patch(API_ROOT + path,
                          data=data, json=json,
                          headers={'Accept': 'application/json'},
                          auth=self.oauth,
                          **kwargs)

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

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


class Wrapper(object):
  def __init__(self, smugmug, json):
    self._smugmug = smugmug
    self._json = json

  def get(self, endpoint, **kwargs):
    uri = self.uri(endpoint)
    return self._smugmug.get(uri, **kwargs) if uri else None

  def post(self, endpoint, data=None, json=None, **kwargs):
    uri = self.uri(endpoint)
    if not uri:
      return None
    return self._smugmug.post(uri, data, json, **kwargs)

  def patch(self, endpoint, data=None, json=None, **kwargs):
    uri = self.uri(endpoint)
    return self._smugmug.patch(uri, data, json, **kwargs)

  def upload(self, endpoint, filename, data, headers=None):
    uri = self.uri(endpoint)
    return self._smugmug.upload(uri, filename, data, headers)

  def uri(self, endpoint):
    return self._json['Uris'].get(endpoint, {}).get('Uri')

  def __getitem__(self, index):
    item = self._json[index]
    if isinstance(item, (dict, list)):
      return Wrapper(self._smugmug, item)
    else:
      return item

  def __len__(self):
    return len(self._json)

  def __eq__(self, other):
    return self._json == other

  def __ne__(self, other):
    return self._json != other

  @property
  def json(self):
    return self._json


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

  @property
  def fs(self):
    return self._fs

  def get_json(self, path, **kwargs):
    return requests.get(API_ROOT + path,
                        headers={'Accept': 'application/json'},
                        auth=self.oauth,
                        **kwargs).json()

  def get(self, path, **kwargs):
    reply = self.get_json(path + '?count=100000', **kwargs)
    response = reply['Response']
    locator = response['Locator']
    return Wrapper(self, response[locator]) if locator in response else None

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
    super(FakeSmugMug, self).__init__(config or {})

  @property
  def service(self):
    return None

  @property
  def oauth(self):
    return None

# Main interface to the SmugMug web service.

import json
import requests
import smugmug_oauth
import smugmug_fs

API_ROOT = 'https://api.smugmug.com'
API_REQUEST = 'https://api.smugmug.com/api/developer/apply'


class Error(Exception):
  """Base class for all exception of this module."""


class NotLoggedInError(Error):
  """Error raised if the user is not logged in."""


class Wrapper(object):
  def __init__(self, smugmug, json):
    self._smugmug = smugmug
    self._json = json

  def get(self, name, **kwargs):
    uri = self._json['Uris'].get(name, {}).get('Uri')
    return self._smugmug.get(uri, **kwargs) if uri else None

  def post(self, name, data=None, json=None, **kwargs):
    uri = self._json['Uris'].get(name, {}).get('Uri')
    if not uri:
      return None
    return self._smugmug.post(uri, data, json, **kwargs)

  def __getitem__(self, index):
    item = self._json[index]
    if isinstance(item, (dict, list)):
      return Wrapper(self._smugmug, item)
    else:
      return item

  def __len__(self):
    return len(self._json)

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
    reply = self.get_json(path, **kwargs)
    response = reply['Response']
    locator = response['Locator']
    return Wrapper(self, response[locator]) if locator in response else None

  def post(self, path, data=None, json=None, **kwargs):
    return requests.post(API_ROOT + path,
                         data=data, json=json,
                         headers={'Accept': 'application/json'},
                         auth=self.oauth,
                         **kwargs)


class FakeSmugMug(SmugMug):
  def __init__(self, config=None):
    super(FakeSmugMug, self).__init__(config or {})

  @property
  def service(self):
    return None

  @property
  def oauth(self):
    return None

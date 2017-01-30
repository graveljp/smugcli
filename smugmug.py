# Main interface to the SmugMug web service.

import json
import persistent_dict
import smugmug_oauth
import smugmug_fs


API_ROOT = 'https://api.smugmug.com'


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
  def __init__(self, config_file):
    try:
      self._config = persistent_dict.PersistentDict(config_file)
    except persistent_dict.InvalidFileError:
      print ('Config file (%s) is invalid. '
             'Please fix or delete the file.' % config_file)
      sys.exit(0)
    self._smugmug_oauth = None
    self._session = None
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
  def session(self):
    if not self._session:
      service = self.service
      if 'access_token' in self.config:
        self._session = service.open_session(self.config['access_token'])
      else:
        print 'User not logged in. Please run the "login" command'
        raise NotLoggedInError
    return self._session

  @property
  def fs(self):
    return self._fs

  def get_json(self, path, **kwargs):
    return self.session.get(
      API_ROOT + path,
      headers={'Accept': 'application/json'},
      **kwargs).json()

  def get(self, path, **kwargs):
    reply = self.get_json(path, **kwargs)
    response = reply['Response']
    locator = response['Locator']
    return Wrapper(self, response[locator]) if locator in response else None

  def post(self, path, data=None, json=None, **kwargs):
    return self.session.post(API_ROOT + path,
                             data=data, json=json,
                             headers={'Accept': 'application/json'},
                             **kwargs)

  def logout(self):
    if 'api_key' in self.config:
      del self.config['api_key']
    if 'access_token' in self.config:
      del self.config['access_token']
    self._service = None
    self._session = None


class FakeSmugMug(object):
  def __init__(self, responses):
    self._responses = responses
    self._fs = smugmug_fs.SmugMugFS(self)

  @property
  def fs(self):
    return self._fs

  def get_json(self, path, params=None):
    return self._responses[path]

  def get(self, path, params=None):
    reply = self.get_json(path, params)
    response = reply['Response']
    locator = response['Locator']
    return Wrapper(self, response[locator])

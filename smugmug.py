# Main interface to the SmugMug web service.

import persistent_dict
import smugmug_oauth

class Error(Exception):
  """Base class for all exception of this module."""
 

class NotLoggedInError(Error):
  """Error raised if the user is not logged in."""


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

  def logout(self):
    if 'api_key' in self.config:
      del self.config['api_key']
    if 'access_token' in self.config:
      del self.config['access_token']
    self._service = None
    self._session = None

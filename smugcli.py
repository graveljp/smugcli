#!/usr/bin/python
# Command line tool for SmugMug. Uses SmugMug API V2.

import argparse
import cmd
import rauth
import urllib
import urlparse
import bottle
import threading
import webbrowser
from wsgiref.simple_server import make_server
import os
import json

OAUTH_ORIGIN = 'https://secure.smugmug.com'
REQUEST_TOKEN_URL = OAUTH_ORIGIN + '/services/oauth/1.0a/getRequestToken'
ACCESS_TOKEN_URL = OAUTH_ORIGIN + '/services/oauth/1.0a/getAccessToken'
AUTHORIZE_URL = OAUTH_ORIGIN + '/services/oauth/1.0a/authorize'

API_REQUEST = 'https://api.smugmug.com/api/developer/apply'
API_ORIGIN = 'https://api.smugmug.com'

CONFIG_FILE = os.path.expanduser('~/.smugcli')

class Error(Exception):
  pass

class NotLoggedInError(Error):
  pass

class SmugMugConfig(dict):
  def __init__(self, path):
    super(SmugMugConfig, self).__init__()
    self._path = path
    self.update(self._read_config())

  def _read_config(self):
    print 'Using config file: %s' % self._path
    try:
      return json.load(open(self._path))
    except IOError:
      # No config found. Default to empty config.
      return {}
    except ValueError:
      print 'WARNING: the config file (%s) is not valid JSON.' % path
      return {}

    if not isinstance(config, dict):
      print 'WARNING: the config file (%s) constains unexpected JSON.' % self._path
      return {}

  def _save_config(self):
    print 'Saving configs to file: %s' % self._path
    with open(self._path, 'w') as handle:
      json.dump(self, handle, sort_keys=True, indent=2, separators=(',', ': '))
    
  def __delitem__(self, key):
    super(SmugMugConfig, self).__delitem__(key)
    self._save_config()

  def __setitem__(self, key, value):
    super(SmugMugConfig, self).__setitem__(key, value)
    self._save_config()


class SmugMugOAuth(object):
  def __init__(self, api_key):
    self._service = self._create_service(api_key)

  def request_access_token(self):
    state = {'running': True}
    app = bottle.Bottle()
    app.route('/', callback=lambda s=state: self._index(s))
    app.route('/callback', callback=lambda s=state: self._callback(s))
    httpd = make_server('localhost', 8080, app)

    def _handle_requests(httpd, state):
      try:
        while state['running']:
          httpd.handle_request()
      except:
        pass
    thread = threading.Thread(target=_handle_requests,
                              args=(httpd, state))
    thread.daemon = True
    try:
      thread.start()
      webbrowser.open('http://localhost:8080/')
      while thread.isAlive():
        thread.join(1)
    finally:
      httpd.server_close()

    return state['access_token'], state['access_token_secret']
  
  def open_session(self, access_token):
    return rauth.OAuth1Session(
      self._service.consumer_key,
      self._service.consumer_secret,
      access_token=access_token[0],
      access_token_secret=access_token[1])

  def _create_service(self, key):
    return rauth.OAuth1Service(
      name='smugcli',
      consumer_key=key[0],
      consumer_secret=key[1],
      request_token_url=REQUEST_TOKEN_URL,
      access_token_url=ACCESS_TOKEN_URL,
      authorize_url=AUTHORIZE_URL,
      base_url=API_ORIGIN + '/api/v2')
  
  def _index(self, state):
    """This route is where our client goes to begin the authorization process."""
    (state['request_token'],
     state['request_token_secret']) = self._service.get_request_token(
       params={'oauth_callback': 'http://localhost:8080/callback'})

    auth_url = self._service.get_authorize_url(state['request_token'])
    auth_url = self._add_auth_params(auth_url, access='Full', permissions='Modify')
    bottle.redirect(auth_url)

  def _callback(self, state):
    """This route is where we receive the callback after the user accepts or
      rejects the authorization request."""
    (state['access_token'],
     state['access_token_secret']) = self._service.get_access_token(
       state['request_token'], state['request_token_secret'],
       params={'oauth_verifier': bottle.request.query['oauth_verifier']})
  
    state['running'] = False
    return 'Success'

  def _add_auth_params(self, auth_url, access, permissions):
    parts = urlparse.urlsplit(auth_url)
    query = urlparse.parse_qsl(parts.query, True)
    query.append(('Access', access))
    query.append(('Permissions', permissions))
    new_query = urllib.urlencode(query, True)
    return urlparse.urlunsplit(
      (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


class SmugMug(object):
  def __init__(self):
    self._config = SmugMugConfig(CONFIG_FILE)
    self._smugmug_oauth = None
    self._session = None

  @property
  def config(self):
    return self._config
  
  @property
  def service(self):
    if not self._smugmug_oauth:
      if 'api_key' in self.config:
        self._smugmug_oauth = SmugMugOAuth(self.config['api_key'])
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
    

def do_login(smugmug, args):
  print 'do_login %s' % args
  parser = argparse.ArgumentParser(
    description='Login onto the SmugMug service')
  parser.add_argument('--key', type=str, required=True, help='SmugMug API key')
  parser.add_argument('--secret', type=str, required=True, help='SmugMug API secret')
  parsed = parser.parse_args(args)

  smugmug.config['api_key'] = (parsed.key, parsed.secret)
  smugmug.config['access_token'] = smugmug.service.request_access_token()


def do_logout(smugmug, args):
  smugmug.logout()


def do_get(smugmug, args):
  result = smugmug.session.get(API_ORIGIN + args[0],
                               headers={'Accept': 'application/json'}).text
  print json.dumps(json.loads(result),
                   sort_keys=True,
                   indent=4,
                   separators=(',', ': '))
  
  
def do_shell(smugmug, args):
  shell = SmugMugShell(smugmug)
  shell.cmdloop()


class SmugMugShell(cmd.Cmd):
  intro = 'Welcome to the SmugMug shell.   Type help or ? to list commands.\n'
  prompt = '(smugmug) '
  file = None

  def __init__(self, smugmug):
    cmd.Cmd.__init__(self)
    self._smugmug = smugmug

  @classmethod
  def set_commands(cls, commands):
    def build_handler(callback):
      def handler(self, args):
        try:
          callback(self._smugmug, args.split())
        except:
          pass
      return handler
    
    for command, callback in commands.iteritems():
      setattr(cls, 'do_' + command, build_handler(callback))

def main():  
  commands = {
    'login': do_login,
    'logout': do_logout,
    'get': do_get,
    'shell': do_shell,
  }
  
  SmugMugShell.set_commands(commands)
  
  parser = argparse.ArgumentParser(description='SmugMug commandline interface.')
  parser.add_argument('command', type=str, choices=commands.keys(),
                 help='The command to run.')
  parser.add_argument('args', nargs=argparse.REMAINDER)
  args = parser.parse_args()

  smugmug = SmugMug()
  commands[args.command](smugmug, args.args)


if __name__ == '__main__':
  main()

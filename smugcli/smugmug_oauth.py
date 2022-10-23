# SumgMug OAuth client

from dataclasses import dataclass
from typing import Any, MutableMapping, Optional, Tuple
import bottle
import rauth
import requests_oauthlib
import signal
import socket
import subprocess
import sys
import threading
from urllib import parse
import webbrowser

OAUTH_ORIGIN = 'https://secure.smugmug.com'
REQUEST_TOKEN_URL = OAUTH_ORIGIN + '/services/oauth/1.0a/getRequestToken'
ACCESS_TOKEN_URL = OAUTH_ORIGIN + '/services/oauth/1.0a/getAccessToken'
AUTHORIZE_URL = OAUTH_ORIGIN + '/services/oauth/1.0a/authorize'

API_ORIGIN = 'https://api.smugmug.com'


class Error(Exception):
  """Base class for all exception of this module."""


class LoginError(Error):
  """Raised on login errors."""


@dataclass
class ApiKey:
  key: str
  secret: str


@dataclass
class RequestToken:
  token: str
  secret: str


@dataclass
class AccessToken:
  token: str
  secret: str


@dataclass
class _State:
  running: bool
  port: int
  app: bottle.Bottle
  request_token: Optional[RequestToken] = None
  access_token: Optional[AccessToken] = None


class SmugMugOAuth(object):

  def __init__(self, api_key: ApiKey):
    self._service = self._create_service(api_key)

  def _get_free_port(self) -> int:
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

  def request_access_token(self) -> AccessToken:
    port = self._get_free_port()
    state = _State(running=True, port=port, app=bottle.Bottle())
    state.app.route('/', callback=lambda s=state: self._index(s))
    state.app.route('/callback', callback=lambda s=state: self._callback(s))

    def abort(signum, frame):
      print('SIGINT received, aborting...')
      state.app.close()
      state.running=False
      sys.exit(1)
    signal.signal(signal.SIGINT, abort)

    def _start_web_server() -> None:
      bottle.run(state.app, port=port)
    thread = threading.Thread(target=_start_web_server)
    thread.daemon = True

    try:
      thread.start()

      login_url = 'http://localhost:%d/' % port
      print('Started local server.')
      print('Visit %s to grant SmugCli access to your SmugMug account.' % login_url)
      print('Opening %s in default browser...' % login_url)
      if self._is_cygwin():
        try:
          return_code = subprocess.call(['cygstart', login_url],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
          success = (return_code == 0)
        except:
          success = False
      else:
        success = webbrowser.open(login_url)

      if not success:
        print('Could not start default browser automatically.')
        print('Please visit %s to complete login process.' % login_url)

      while state.running and thread.is_alive():
        thread.join(1)
    finally:
      state.app.close()

    if state.access_token is None:
      raise LoginError("Failed requesting access token.")

    return state.access_token

  def get_oauth(
      self, access_token: AccessToken) -> requests_oauthlib.OAuth1:
    return requests_oauthlib.OAuth1(
        self._service.consumer_key,
        self._service.consumer_secret,
        resource_owner_key=access_token.token,
        resource_owner_secret=access_token.secret)

  def _create_service(self, api_key: ApiKey) -> rauth.OAuth1Service:
    return rauth.OAuth1Service(
      name='smugcli',
      consumer_key=api_key.key,
      consumer_secret=api_key.secret,
      request_token_url=REQUEST_TOKEN_URL,
      access_token_url=ACCESS_TOKEN_URL,
      authorize_url=AUTHORIZE_URL,
      base_url=API_ORIGIN + '/api/v2')

  def _index(self, state: _State) -> None:
    """This route is where our client goes to begin the authorization process."""
    request_token, request_token_secret = self._service.get_request_token(
       params={'oauth_callback': 'http://localhost:%d/callback' % state.port})
    state.request_token = RequestToken(
      token=request_token, secret=request_token_secret)

    auth_url = self._service.get_authorize_url(request_token)
    auth_url = self._add_auth_params(auth_url, access='Full', permissions='Modify')
    bottle.redirect(auth_url)

  def _callback(self, state: _State) -> str:
    """This route is where we receive the callback after the user accepts or
      rejects the authorization request."""
    if state.request_token is None:
      raise LoginError("No request token obtained.")

    oauth_verifier = bottle.request.query['oauth_verifier']  # type: ignore
    (token, secret) = self._service.get_access_token(
       state.request_token.token, state.request_token.secret,
       params={'oauth_verifier': oauth_verifier})
    state.access_token = AccessToken(token, secret)

    state.app.close()
    state.running = False
    return 'Login successful. You may close this window.'

  def _add_auth_params(
      self, auth_url: str, access: str, permissions: str) -> str:
    parts = parse.urlsplit(auth_url)
    query = parse.parse_qsl(parts.query, True)
    query.append(('Access', access))
    query.append(('Permissions', permissions))
    new_query = parse.urlencode(query, True)
    return parse.urlunsplit(
      (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))

  def _is_cygwin(self) -> bool:
    try:
      return_code = subprocess.call(['which', 'cygstart'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
      return (return_code == 0)
    except:
      return False

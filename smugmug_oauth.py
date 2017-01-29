# SumgMug OAuth client

import bottle
import rauth
import socket
import threading
import urllib
import urlparse
import webbrowser
from wsgiref.simple_server import make_server

OAUTH_ORIGIN = 'https://secure.smugmug.com'
REQUEST_TOKEN_URL = OAUTH_ORIGIN + '/services/oauth/1.0a/getRequestToken'
ACCESS_TOKEN_URL = OAUTH_ORIGIN + '/services/oauth/1.0a/getAccessToken'
AUTHORIZE_URL = OAUTH_ORIGIN + '/services/oauth/1.0a/authorize'

API_ORIGIN = 'https://api.smugmug.com'

class SmugMugOAuth(object):
  def __init__(self, api_key):
    self._service = self._create_service(api_key)

  def _get_free_port(self):
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port
  
  def request_access_token(self):
    port = self._get_free_port()
    state = {'running': True, 'port': port}
    app = bottle.Bottle()
    app.route('/', callback=lambda s=state: self._index(s))
    app.route('/callback', callback=lambda s=state: self._callback(s))
    httpd = make_server('', port, app)

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
      webbrowser.open('http://localhost:%d/' % port)
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
       params={'oauth_callback': 'http://localhost:%d/callback' % state['port']})

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

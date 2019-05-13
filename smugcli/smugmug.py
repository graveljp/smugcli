# Main interface to the SmugMug web service.

from . import smugmug_oauth

import base64
import collections
import hashlib
import heapq
import io
import json
import math
import os
import re
import requests
import threading
import time

API_ROOT = 'https://api.smugmug.com'
API_UPLOAD = 'https://upload.smugmug.com/'
API_REQUEST = 'https://api.smugmug.com/api/developer/apply'

PAGE_START_RE = re.compile(r'(\?.*start=)[0-9]+')

class Error(Exception):
  """Base class for all exception of this module."""


class InvalidArgumentError(Error):
  """Error raised when an invalid argument is specified."""


class NotLoggedInError(Error):
  """Error raised if the user is not logged in."""


class RemoteDataError(Error):
  """Error raised when the remote structure is incompatible with SmugCLI."""


class UnexpectedResponseError(Error):
  """Error raised when encountering unexpected data returned by SmugMug."""


class InterruptedError(Error):
  """Error raised when a network operation is interrupted."""


class ChildCacheGarbageCollector(object):
  """Garbage collector for clearing the node's children cache.

  Because multiple threads could process the same nodes in parallel, the nodes
  and their children are cached so that we only fetch nodes once form the
  server. It's important to eventually clear this cache though, otherwise the
  JSON data of the whole SmugMug account could end up being stored in memory
  after a complete sync.  This garbage collector trims the node tree by clearing
  out the node's children cache, keeping the number of cached nodes under a
  certain threshold. Nodes are discarded by clearing the nodes that were visited
  the longest ago first.
  """

  def __init__(self, max_nodes):
    self._max_nodes = max_nodes
    self._oldest = []
    self._nodes = {}
    self._mutex = threading.Lock()
    self._DELETED = '__DELETED__'
    self._age_index = 0

  def set_max_children_cache(self, max_nodes):
    """Set the maximum number of children cache to keep in memory.

    As a rule of thumb, the number of cached nodes should be proportional to the
    number of threads processing the tree.

    Args:
      max_nodes: int, the number of nodes that should be allows to keep a
          children cache.
    """
    self._max_nodes = max_nodes

  def _get_next_age_index(self):
    age_index = self._age_index
    self._age_index += 1
    return age_index

  def visited(self, node):
    """Record a node as just visited and clear the cache of the oldest visit.

    Args:
      node: Node object, the node object to mark as visited.
    """
    with self._mutex:
      if node in self._nodes:
        self._nodes[node][0] = self._get_next_age_index()
        heapq.heapify(self._oldest)
      else:
        new_entry = [self._get_next_age_index(), node]
        self._nodes[node] = new_entry
        heapq.heappush(self._oldest, new_entry)

        while len(self._nodes) > self._max_nodes:
          node_to_clear = heapq.heappop(self._oldest)[1]
          node_to_clear.reset_cache()
          del self._nodes[node_to_clear]


class NodeList(object):
  def __init__(self, smugmug, json, parent):
    self._smugmug = smugmug
    self._parent = parent

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

    page_index = int(item / self._page_size)
    if self._pages[page_index] is None:
      new_page_uri = self._uri % (page_index * self._page_size + 1)
      json = self._smugmug.get_json(new_page_uri)
      response = json['Response']
      locator = response['Locator']
      self._pages[page_index] = response[locator]
    return Node(self._smugmug,
                self._pages[page_index][item - page_index * self._page_size],
                self._parent)


class Node(object):
  def __init__(self, smugmug, json, parent=None):
    self._smugmug = smugmug
    self._json = json
    self._parent = parent
    self._child_nodes_by_name = None
    self._lock = threading.Lock()

  @property
  def json(self):
    return self._json

  @property
  def name(self):
    return self._json.get('FileName') or self._json['Name']

  @property
  def path(self):
    if self._parent is not None:
      return os.path.join(self._parent.path, self.name)
    else:
      return self.name

  def get(self, url_name, **kwargs):
    uri = self.uri(url_name)
    return self._smugmug.get(uri, parent=self, **kwargs)

  def post(self, uri_name, data=None, json=None, **kwargs):
    uri = self.uri(uri_name)
    return self._smugmug.post(uri, data, json, **kwargs)

  def patch(self, uri_name, data=None, json=None, **kwargs):
    uri = self.uri(uri_name)
    return self._smugmug.patch(uri, data, json, **kwargs)

  def delete(self, **kwargs):
    uri = self._json.get('Uri')
    return self._smugmug.delete(uri, **kwargs)

  def upload(self, uri_name, filename, data, progress_fn=None, headers=None):
    uri = self.uri(uri_name)
    return self._smugmug.upload(uri, filename, data, progress_fn, headers)

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

  def __hash__(self):
    return id(self)

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

  def _get_child_nodes_by_name(self):
    if self._child_nodes_by_name is None:
      self._child_nodes_by_name = collections.defaultdict(list)
      for child in self.get_children():
        self._child_nodes_by_name[child.name].append(child)

    self._smugmug.garbage_collector.visited(self)
    return self._child_nodes_by_name

  def _create_child_node(self, name, params):
    if self._json['Type'] != 'Folder':
      raise InvalidArgumentError(
        'Nodes can only be created in folders.\n'
        '"%s" is of type "%s".' % (self.name, self._json['Type']))

    if name in self._get_child_nodes_by_name():
      raise InvalidArgumentError('Node %s already exists in folder %s' % (
                                 name, self.name))

    remote_name = name.strip()
    node_params = {
      'Name': remote_name,
      'Privacy': 'Public',
      'SortDirection': 'Ascending',
      'SortMethod': 'Name',
    }
    node_params.update(params or {})

    print('Creating %s "%s".' % (params['Type'], os.path.join(self.path,
                                                              remote_name)))
    response = self.post('ChildNodes', data=sorted(node_params.items()))
    if response.status_code != 201:
      raise UnexpectedResponseError(
        'Error creating node "%s".\n'
        'Server responded with status code %d: %s.' % (
          name, response.status_code, response.json()['Message']))

    node_json = response.json().get('Response', {}).get('Node')
    if not node_json:
      raise UnexpectedResponseError('Cannot resolve created node JSON')

    node = Node(self._smugmug, node_json, parent=self)
    node._child_nodes_by_name = {}
    self._smugmug.garbage_collector.visited(node)
    self._get_child_nodes_by_name()[name] = [node]

    if node['Type'] == 'Album':
      response = node.patch('Album', json={'SortMethod': 'DateTimeOriginal'})
      if response.status_code != 200:
        print('Failed setting SortMethod on Album "%s".' % name)
        print('Server responded with status code %d: %s.' % (
          response.status_code, response.json()['Message']))
    return node

  def get_child(self, name):
    with self._lock:
      match = self._get_child_nodes_by_name().get(name)

    if not match:
      return None

    if len(match) > 1:
      raise RemoteDataError(
        'Multiple remote nodes matches "%s" in node "%s".' % (name, self.name))

    return match[0]

  def get_or_create_child(self, name, params):
    with self._lock:
      match = self._get_child_nodes_by_name().get(name)
      if not match:
        return self._create_child_node(name, params)

    if len(match) > 1:
      raise RemoteDataError(
        'Multiple remote nodes matches "%s" in node "%s".' % (name, self.name))

    return match[0]

  def reset_cache(self):
    with self._lock:
      self._child_nodes_by_name = None


def Wrapper(smugmug, json, parent=None):
  response = json['Response']
  if 'Pages' in response:
    return NodeList(smugmug, json, parent)
  else:
    locator = response['Locator']
    endpoint = response[locator]
    return Node(smugmug, endpoint, parent)


class StreamingUpload(object):
  def __init__(self, data, progress_fn, chunk_size=1<<13):
    self._data = io.BytesIO(data)
    self._len = len(data)
    self._progress_fn = progress_fn
    self._progress = 0

  def __len__(self):
    return self._len

  def read(self, n=-1):
    chunk = self._data.read(n)
    self._progress += len(chunk)
    if self._progress_fn:
      aborting = self._progress_fn(100 * self._progress / self._len)
      if aborting:
        raise InterruptedError('File transfer interrupted.')
    return chunk

  def tell(self):
    return self._data.tell()

  def seek(self, offset, whence=0):
    self._data.seek(offset, whence)


class SmugMug(object):
  def __init__(self, config, requests_sent=None):
    self._config = config
    self._smugmug_oauth = None
    self._oauth = None
    self._user_root_node = None
    self._session = requests.Session()
    self._requests_sent = requests_sent
    self._garbage_collector = ChildCacheGarbageCollector(8)

  @property
  def config(self):
    return self._config

  @property
  def garbage_collector(self):
    return self._garbage_collector

  @property
  def service(self):
    if not self._smugmug_oauth:
      if 'api_key' in self.config:
        self._smugmug_oauth = smugmug_oauth.SmugMugOAuth(self.config['api_key'])
      else:
        print('No API key provided.')
        print('Please request an API key at %s' % API_REQUEST)
        print('and run "smugcli.py login"')
        raise NotLoggedInError
    return self._smugmug_oauth

  @property
  def oauth(self):
    if not self._oauth:
      if self.service and 'access_token' in self.config:
        self._oauth = self.service.get_oauth(self.config['access_token'])
      else:
        print('User not logged in. Please run the "login" command')
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
    if 'authuser' in self.config:
      del self.config['authuser']
    if 'authuser_uri' in self.config:
      del self.config['authuser_uri']
    self._service = None
    self._session = None

  def get_auth_user(self):
    if not 'authuser' in self.config:
      self.config['authuser'] = self.get('/api/v2!authuser')['NickName']
    return self.config['authuser']

  def get_user_uri(self, user):
    return self.get('/api/v2/user/%s' % user).uri('Node')

  def get_auth_user_uri(self):
    if not 'authuser_uri' in self._config:
      self.config['authuser_uri'] = self.get_user_uri(self.get_auth_user())
    return self.config['authuser_uri']

  def get_auth_user_root_node(self):
    if self._user_root_node is None:
      self._user_root_node = self.get(self.get_auth_user_uri())
    return self._user_root_node

  def get_root_node(self, user):
    if user == self.get_auth_user():
      return self.get_auth_user_root_node()
    else:
      return self.get(self.get_user_uri(user))

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

  def get(self, path, parent=None, **kwargs):
    reply = self.get_json(path, **kwargs)
    return Wrapper(self, reply, parent)

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
    req = requests.Request('PATCH',
                           API_ROOT + path,
                           data=data, json=json,
                           headers={'Accept': 'application/json'},
                           auth=self.oauth,
                           **kwargs).prepare()
    resp = self._session.send(req)
    if self._requests_sent is not None:
      self._requests_sent.append((req, resp))
    return resp

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

  def upload(self, uri, filename, data, progress_fn=None,
             additional_headers=None):
    headers = {'Content-Length': str(len(data)),
               'Content-MD5': base64.b64encode(hashlib.md5(data).digest()),
               'X-Smug-AlbumUri': uri,
               'X-Smug-FileName': filename,
               'X-Smug-ResponseType': 'JSON',
               'X-Smug-Version': 'v2'}
    headers.update(additional_headers or {})
    req = requests.Request('POST',
                           API_UPLOAD,
                           data=StreamingUpload(data, progress_fn),
                           headers=headers,
                           auth=self.oauth).prepare()
    resp = self._session.send(req)
    if self._requests_sent is not None:
      self._requests_sent.append((req, resp))
    return resp


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

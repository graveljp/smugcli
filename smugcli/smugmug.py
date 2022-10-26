"""Python interface to SmugMug's V2 API."""

from typing import Any, List, MutableMapping, MutableSequence, Optional, Tuple
from typing import Union

import base64
import collections
import hashlib
import heapq
import io
import math
import os
import re
import threading

import requests
import requests_oauthlib

from . import smugmug_oauth

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


class ConnectionInterruptedError(Error):
  """Error raised when a network operation is interrupted."""


class ChildCacheGarbageCollector():
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
    self._age_index = 0

  @property
  def nodes(self):
    """Returns the list of nodes held in the cache."""
    return self._nodes

  @property
  def oldest(self):
    """Returns a heap of the nodes ordered by age."""
    return self._oldest

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


class NodeList():
  """A list of JSON node returned by SmugMug."""

  def __init__(self, smugmug: 'SmugMug', json, parent):
    self._smugmug = smugmug
    self._parent = parent

    response = json['Response']
    locator = response['Locator']
    page_info = response['Pages']
    self._page_size = page_info['Count']
    self._total_size = page_info['Total']
    num_pages = int(math.ceil(float(self._total_size) / self._page_size)
                    if self._page_size else 0)
    self._pages = [None] * num_pages  # type: MutableSequence[Any]
    if num_pages:
      self._pages[0] = response[locator]
    self._uri = PAGE_START_RE.sub(r'\1%d', response['Uri'])

  def __len__(self) -> int:
    return self._total_size

  def __getitem__(self, item) -> 'Node':
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


class Node():
  """A single JSON object node returned by SmugMug."""

  def __init__(
      self,
      smugmug: 'SmugMug',
      json,
      parent: Optional['Node'] = None,
      child_nodes_by_name: Optional[MutableMapping[str, List['Node']]] = None
  ) -> None:
    self._smugmug = smugmug
    self._json = json
    self._parent = parent
    self._child_nodes_by_name = child_nodes_by_name
    self._lock = threading.Lock()

  @property
  def json(self):
    """Returns the JSON data this node holds."""
    return self._json

  @property
  def name(self) -> str:
    """Extracts the name of this node from the JSON data."""
    value = self._json.get('FileName') or self._json['Name']
    if not isinstance(value, str):
      raise UnexpectedResponseError(
          f'Expected node name to be a string, but got {value}.')
    return value

  @property
  def path(self) -> str:
    """Returns the path to this node in the node hierarchy."""
    if self._parent is not None:
      return os.path.join(self._parent.path, self.name)
    return self.name

  def get_node(self, url_name, **kwargs) -> 'Node':
    """Queries this node's `url_name` child, expecting it to be a node."""
    uri = self.uri(url_name)
    return self._smugmug.get_node(uri, parent=self, **kwargs)

  def get_list(self, url_name, **kwargs) -> NodeList:
    """Queries this node's `url_name` child, expecting it to be a node list."""
    uri = self.uri(url_name)
    return self._smugmug.get_list(uri, parent=self, **kwargs)

  def post(self, uri_name: str, data=None, json=None, **kwargs):
    """Does a POST request to this node's `uri_name` endpoint."""
    uri = self.uri(uri_name)
    return self._smugmug.post(uri, data, json, **kwargs)

  def patch(self, uri_name, data=None, json=None, **kwargs):
    """Does a PATCH request to this node's `uri_name` endpoint."""
    uri = self.uri(uri_name)
    return self._smugmug.patch(uri, data, json, **kwargs)

  def delete(self, **kwargs):
    """Does a DELETE request to this node's `uri_name` endpoint."""
    uri = self._json.get('Uri')
    return self._smugmug.delete(uri, **kwargs)

  def upload(self, uri_name, filename, data, progress_fn=None, headers=None):
    """Does an UPLOAD request to this node's `uri_name` endpoint."""
    uri = self.uri(uri_name)
    return self._smugmug.upload(uri, filename, data, progress_fn, headers)

  def uri(self, url_name: str) -> str:
    """Returns the uri of this node's `url_name` child."""
    uri = self._json.get('Uris', {}).get(url_name, {}).get('Uri')
    if not uri:
      raise UnexpectedResponseError(f'Node does not have a "{url_name}" uri.')
    if not isinstance(uri, str):
      raise UnexpectedResponseError(
          f'Expected uri "{url_name}" to be a string, but got: "{repr(uri)}".')
    return uri

  def __getitem__(self, key: str):
    return self._json[key]

  def __contains__(self, key: str):
    return key in self._json

  def __eq__(self, other):
    return self._json == other

  def __ne__(self, other):
    return self._json != other

  def __hash__(self):
    return id(self)

  def get_children(self, params=None) -> NodeList:
    """Get the children list of this node."""
    if 'Type' not in self._json:
      raise UnexpectedResponseError('Node does not have a "Type" attribute.')

    params = params or {}
    params = {
        'start': params.get('start', 1),
        'count': params.get('count',
                            self._smugmug.config.get('page_size', 1000))}

    if self._json['Type'] == 'Album':
      return self.get_node('Album').get_list('AlbumImages', params=params)
    return self.get_list('ChildNodes', params=params)

  def _get_child_nodes_by_name(self) -> MutableMapping[str, List['Node']]:
    if self._child_nodes_by_name is None:
      self._child_nodes_by_name = collections.defaultdict(list)
      for child in self.get_children():
        self._child_nodes_by_name[child.name].append(child)

    self._smugmug.garbage_collector.visited(self)
    return self._child_nodes_by_name

  def _create_child_node(self, name: str, params) -> 'Node':
    node_type = self._json['Type']
    if node_type != 'Folder':
      raise InvalidArgumentError(
          'Nodes can only be created in folders.\n'
          f'"{self.name}" is of type "{node_type}".')

    if name in self._get_child_nodes_by_name():
      raise InvalidArgumentError(
          f'Node {name} already exists in folder {self.name}')

    remote_name = name.strip()
    node_params = {
        'Name': remote_name,
        'Privacy': 'Public',
        'SortDirection': 'Ascending',
        'SortMethod': 'Name',
    }
    node_params.update(params or {})

    child_type = params['Type']
    print(f'Creating {child_type} "{os.path.join(self.path, remote_name)}".')
    response = self.post('ChildNodes', data=sorted(node_params.items()))

    try:
      response_json = response.json()
    except requests.exceptions.JSONDecodeError as exc:
      raise UnexpectedResponseError(
          f'Error creating node "{name}".\n'
          'Expected a JSON response from SmugMug service.') from exc

    node_json = response_json.get('Response', {}).get('Node')
    if not node_json:
      raise UnexpectedResponseError('Cannot resolve created node JSON')

    node = Node(self._smugmug, node_json, parent=self,
                child_nodes_by_name={})
    self._smugmug.garbage_collector.visited(node)
    self._get_child_nodes_by_name()[name] = [node]

    if node['Type'] == 'Album':
      node.patch('Album', json={'SortMethod': 'DateTimeOriginal'})
    return node

  def get_child(self, name: str) -> Union['Node', None]:
    """Returns this node's child named `name`."""
    with self._lock:
      match = self._get_child_nodes_by_name().get(name)

    if not match:
      return None

    if len(match) > 1:
      raise RemoteDataError(
          f'Multiple remote nodes matches "{name}" in node "{self.name}".')

    return match[0]

  def get_or_create_child(self, name: str, params) -> 'Node':
    """Returns this node's `name` child, create it if not found."""
    with self._lock:
      match = self._get_child_nodes_by_name().get(name)
      if not match:
        return self._create_child_node(name, params)

    if len(match) > 1:
      raise RemoteDataError(
          f'Multiple remote nodes matches "{name}" in node "{self.name}".')

    return match[0]

  def reset_cache(self) -> None:
    """Reset this node's children cache."""
    with self._lock:
      self._child_nodes_by_name = None


class StreamingUpload():
  """Helper for uploading a data stream to SmugMug."""

  def __init__(self, data, progress_fn):
    self._data = io.BytesIO(data)
    self._len = len(data)
    self._progress_fn = progress_fn
    self._progress = 0

  def __len__(self):
    return self._len

  def read(self, size=-1):
    """Read `size` bytes from stream."""
    chunk = self._data.read(size)
    self._progress += len(chunk)
    if self._progress_fn:
      aborting = self._progress_fn(100 * self._progress / self._len)
      if aborting:
        raise ConnectionInterruptedError('File transfer interrupted.')
    return chunk

  def tell(self):
    """Returns the current stream position."""
    return self._data.tell()

  def seek(self, offset, whence=0):
    """Change the stream position to the given offset."""
    self._data.seek(offset, whence)


class SmugMug():
  """Python interface to SmugMug's V2 API."""

  def __init__(
      self,
      config,
      requests_sent: Optional[List[Tuple[requests.PreparedRequest,
                                         requests.Response]]] = None) -> None:
    self._config = config
    self._smugmug_oauth = None
    self._oauth = None
    self._user_root_node = None
    self._session = requests.Session()
    self._requests_sent = requests_sent
    self._garbage_collector = ChildCacheGarbageCollector(8)

  @property
  def config(self):
    """Returns the config object."""
    return self._config

  @property
  def garbage_collector(self):
    """Returns the garbage collector."""
    return self._garbage_collector

  @property
  def service(self) -> smugmug_oauth.SmugMugOAuth:
    """Creates and returns a SmugMugOAuth instance."""
    if not self._smugmug_oauth:
      if 'api_key' in self.config:
        key, secret = self.config['api_key']
        self._smugmug_oauth = smugmug_oauth.SmugMugOAuth(
            smugmug_oauth.ApiKey(key, secret))
      else:
        print('No API key provided.')
        print(f'Please request an API key at {API_REQUEST}')
        print('and run "smugcli.py login"')
        raise NotLoggedInError
    return self._smugmug_oauth

  @property
  def oauth(self) -> requests_oauthlib.OAuth1:
    """Requests a SmugMug access token."""
    if not self._oauth:
      if self.service and 'access_token' in self.config:
        key, secret = self.config['access_token']
        self._oauth = self.service.get_oauth(
            smugmug_oauth.AccessToken(key, secret))
      else:
        print('User not logged in. Please run the "login" command')
        raise NotLoggedInError
    return self._oauth

  def login(self, key: str, secret: str) -> None:
    """Does an OAuth login to the SmugMug service."""
    self.config['api_key'] = (key, secret)
    access_token = self.service.request_access_token()
    self.config['access_token'] = (access_token.token, access_token.secret)

  def logout(self) -> None:
    """Logout from the SmugMug service."""
    if 'api_key' in self.config:
      del self.config['api_key']
    if 'access_token' in self.config:
      del self.config['access_token']
    if 'authuser' in self.config:
      del self.config['authuser']
    if 'authuser_uri' in self.config:
      del self.config['authuser_uri']

  def get_auth_user(self) -> str:
    """Returns the name of the currently logged-in user."""
    if 'authuser' not in self.config:
      nickname = self.get_node('/api/v2!authuser')['NickName']
      if not isinstance(nickname, str):
        raise UnexpectedResponseError(
            'Expected auth user nickname to be a string, but '
            f'got "{repr(nickname)}".')
      self.config['authuser'] = nickname
    return self.config['authuser']

  def get_user_uri(self, user: str) -> str:
    """Returns the specified user's root node URI."""
    return self.get_node(f'/api/v2/user/{user}').uri('Node')

  def get_auth_user_uri(self) -> str:
    """Returns the logged-in user's root node URI."""
    if 'authuser_uri' not in self._config:
      self.config['authuser_uri'] = self.get_user_uri(self.get_auth_user())
    return self.config['authuser_uri']

  def get_auth_user_root_node(self) -> Node:
    """Returns the logged-in user's root node."""
    if self._user_root_node is None:
      self._user_root_node = self.get_node(self.get_auth_user_uri())
    return self._user_root_node

  def get_root_node(self, user: str) -> Node:
    """Returns the specified user's root node."""
    if user == self.get_auth_user():
      return self.get_auth_user_root_node()
    return self.get_node(self.get_user_uri(user))

  def get_json(self, path: str, **kwargs):
    """Queries the specified path and return its JSON payload."""
    req = requests.Request('GET', API_ROOT + path,
                           headers={'Accept': 'application/json'},
                           auth=self.oauth,
                           **kwargs).prepare()
    resp = self._session.send(req)
    if self._requests_sent is not None:
      self._requests_sent.append((req, resp))
    resp.raise_for_status()
    try:
      return resp.json()
    except requests.exceptions.JSONDecodeError as exc:
      raise UnexpectedResponseError(
          f'Error parsing responses from "{path}".\n'
          'Expected a JSON response from SmugMug service.') from exc

  def get_node(
      self, path: str, parent: Optional[Node] = None, **kwargs
  ) -> Node:
    """Queries the specified path and return its content as a `Node`."""
    reply = self.get_json(path, **kwargs)
    response = reply['Response']
    if 'Pages' in reply['Response']:
      raise UnexpectedResponseError(
          f'Expected {path} to be a node, not a list.')
    locator = response['Locator']
    endpoint = response[locator]
    return Node(self, endpoint, parent)

  def get_list(self, path: str, parent=None, **kwargs) -> NodeList:
    """Queries the specified path and return its content as a `NodeList`."""
    reply = self.get_json(path, **kwargs)
    if 'Pages' not in reply['Response']:
      raise UnexpectedResponseError(
          f'Expected {path} to be a list.')
    return NodeList(self, reply, parent)

  def post(self, path: str, data=None, json=None, **kwargs):
    """Does a POST request to the specified path"""
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
    resp.raise_for_status()
    return resp

  def patch(self, path: str, data=None, json=None, **kwargs):
    """Does a PATCH request to the specified path"""
    req = requests.Request('PATCH',
                           API_ROOT + path,
                           data=data, json=json,
                           headers={'Accept': 'application/json'},
                           auth=self.oauth,
                           **kwargs).prepare()
    resp = self._session.send(req)
    if self._requests_sent is not None:
      self._requests_sent.append((req, resp))
    resp.raise_for_status()
    return resp

  def delete(self, path: str, **kwargs):
    """Does a DELETE request to the specified path"""
    req = requests.Request('DELETE',
                           API_ROOT + path,
                           auth=self.oauth,
                           headers={'Accept': 'application/json'},
                           **kwargs).prepare()
    resp = self._session.send(req)
    if self._requests_sent is not None:
      self._requests_sent.append((req, resp))
    resp.raise_for_status()
    return resp

  def upload(self, uri: str, filename: str, data, progress_fn=None,
             additional_headers=None):
    """Does an UPLOAD request to the specified path"""
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
    resp.raise_for_status()
    return resp


class FakeSmugMug(SmugMug):
  """Fake SmugMug object, for unit testing purpose."""

  def __init__(self, config=None):
    config = config or {}
    config['page_size'] = 10
    super().__init__(config or {})

  @property
  def service(self):
    return None

  @property
  def oauth(self):
    return None

import collections
import os

class SmugMugFS(object):
  def __init__(self, smugmug):
    self._smugmug = smugmug

  def get_root_node(self, user):
    return self._smugmug.get('/api/v2/user/%s' % user).get('Node')

  def get_children(self, node, params=None):
    return node.get('ChildNodes') or []

  def get_child(self, parent, child_name, params=None):
    for node in self.get_children(parent, params):
      if node['Name'] == child_name:
        return node
    return None

  def path_to_node(self, user, path):
    current_node = self.get_root_node(user)
    parts = filter(bool, path.split(os.sep))
    last_node = current_node
    matched = []
    unmatched = collections.deque(parts)
    for part in parts:
      current_node = self.get_child(current_node, part)
      if not current_node:
        break
      last_node = current_node
      matched.append(part)
      unmatched.popleft()
    return last_node, matched, list(unmatched)

  def ls(self, user, path, details):
    user = user or self._smugmug.get_auth_user()
    node, matched, unmatched = self.path_to_node(user, path)
    if unmatched:
      print '"%s" not found in folder "%s"' % (unmatched[0], os.sep.join(matched))
      return

    if node['Type'] == 'Album':
      children = node.get('Album').get('AlbumImages') or []
      names = [child['FileName'] for child in children]
    else:
      children = node.get('ChildNodes') or []
      names = [child['Name'] for child in children]

    if details:
      print json.dumps(children.json, sort_keys=True, indent=2,
                       separators=(',', ': '))
    else:
      for name in names:
        print name

  def make_node(self, user, path, create_parents, params=None):
    user = user or self._smugmug.get_auth_user()
    node, matched, unmatched = self.path_to_node(user, path)
    if len(unmatched) > 1 and not create_parents:
      print '"%s" not found in "%s"' % (unmatched[0], os.sep.join(matched))
      return

    if not len(unmatched):
      print 'Path "%s" already exists.' % path
      return

    if node['Type'] != 'Folder':
      print 'Nodes can only be created in folders.'
      print '"%s" is of type "%s".' % (os.sep.join(matched), node['Type'])
      return

    for part in unmatched:
      node_params = {
        'Name': part,
        'UrlName': part.replace(' ', '-').title(),
      }
      node_params.update(params or {})

      response = node.post('ChildNodes', data=node_params)
      if response is None:
        print 'Cannot create child nodes under "%s"' % (
          os.sep.join(matched))
        return

      matched.append(part)

      if response.status_code != 201:
        print 'Error creating node "%s".' % os.sep.join(matched)
        print 'Server responded with %s' % str(response)
        return

      node = self.get_child(node, part)
      if not node:
        print 'Cannot find newly created node "%s"' % os.sep.join(matched)
        return

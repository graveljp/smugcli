import collections
import os

class SmugMugFS(object):
  def __init__(self, smugmug):
    self._smugmug = smugmug

  def get_root_node(self, user):
    return self._smugmug.get('/api/v2/user/%s' % user).get('Node')

  def get_children(self, node, params=None):
    return node.get('ChildNodes') or []

  def get_child(self, node, child_name, params=None):
    for node in self.get_children(node, params):
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

from smugcli import persistent_dict

from os import path
import json
from parameterized import parameterized
import shutil
import tempfile
import unittest


class TestPersistentDict(unittest.TestCase):

  def setUp(self):
    self._test_dir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self._test_dir)

  def test_non_existing_file(self):
    filename = path.join(self._test_dir, 'not_existant_file')
    pdict = persistent_dict.PersistentDict(filename)
    self.assertEqual(pdict, {})

  def test_file_not_created_unless_needed(self):
    filename = path.join(self._test_dir, 'not_existant_file')
    pdict = persistent_dict.PersistentDict(filename)
    self.assertFalse(path.isfile(filename))

    pdict.get('key', 123)
    self.assertFalse(path.isfile(filename))

    pdict['key'] = 123
    self.assertTrue(path.isfile(filename))

  @parameterized.expand([
    ('int', 10),
    ('str', 'foo'),
    ('Unicode', u'\xef'),
    ('list', [1, 2]),
    ('dict', {'foo': 1, 'bar': 'baz'}),
    ('complex_list', [1, {'foo': [3, 4]}]),
    ('complex_dict', {'foo': 1, 'bar': [2, 3]})])
  def test_load_from_existing_file(self, test_name, value):
    filename = path.join(self._test_dir, 'my_file')
    with open(filename, 'w') as handle:
      json.dump({'a': value}, handle)
    pdict = persistent_dict.PersistentDict(filename)
    self.assertEqual(pdict, {'a': value})

  @parameterized.expand([
    ('int', 10, 10),
    ('str', 'foo', 'foo'),
    ('Unicode', u'\xef', u'\xef'),
    ('list', [1, 2], [1, 2]),
    ('tuple', (1, 2), [1, 2]),
    ('dict', {'foo': 1, 'bar': 2}, {'foo': 1, 'bar': 2}),
    ('complex_list', [1, {'foo': (3, 4)}], [1, {'foo': [3, 4]}]),
    ('complex_dict', {'foo': 1, 'bar': [2, 3]}, {'foo': 1, 'bar': [2, 3]})])
  def test_automatically_save_added_fields(self, test_name, value, result):
    filename = path.join(self._test_dir, 'new_file')
    pdict = persistent_dict.PersistentDict(filename)
    pdict['a'] = value
    with open(filename) as f:
      self.assertEqual(json.load(f), {'a': result})

  def test_getattr(self):
    filename = path.join(self._test_dir, 'new_file')
    with open(filename, 'w') as handle:
      json.dump({'a': 'foo'}, handle)
    pdict = persistent_dict.PersistentDict(filename)
    self.assertEqual(pdict['a'], 'foo')

  def test_automatically_save_modified_sub_fields(self):
    filename = path.join(self._test_dir, 'new_file')
    pdict = persistent_dict.PersistentDict(filename)
    pdict['a'] = {'foo': 1, 'bar': [2, 3]}
    pdict['a']['bar'][1] = 4
    del pdict['a']['foo']
    with open(filename) as f:
      self.assertEqual(json.load(f), {'a': {'bar': [2, 4]}})

  def test_automatically_save_deleted_fields(self):
    filename = path.join(self._test_dir, 'my_file')
    with open(filename, 'w') as handle:
      handle.write('{"a": 10, "b": 20}')
    pdict = persistent_dict.PersistentDict(filename)
    del pdict['a']
    with open(filename) as f:
      self.assertEqual(json.load(f), {'b': 20})


if __name__ == '__main__':
  unittest.main()

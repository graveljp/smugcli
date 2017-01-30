from os import path
import json
import persistent_dict
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

  def test_load_from_existing_file(self):
    filename = path.join(self._test_dir, 'my_file')
    with open(filename, 'w') as handle:
      handle.write('{"a": 10}')
    pdict = persistent_dict.PersistentDict(filename)
    self.assertEqual(pdict, {'a': 10})

  def test_automatically_save_added_fields(self):
    filename = path.join(self._test_dir, 'new_file')
    pdict = persistent_dict.PersistentDict(filename)
    pdict['a'] = 10
    self.assertEqual(json.load(open(filename)), {'a': 10})


  def test_automatically_save_deleted_fields(self):
    filename = path.join(self._test_dir, 'my_file')
    with open(filename, 'w') as handle:
      handle.write('{"a": 10, "b": 20}')
    pdict = persistent_dict.PersistentDict(filename)
    del pdict['a']
    self.assertEqual(json.load(open(filename)), {'b': 20})

if __name__ == '__main__':
  unittest.main()

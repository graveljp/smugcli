# dict implementation that automatically saves it's state to a file on disk.

import json

class Error(Exception):
  """Base class for all exception of this module."""

class InvalidFileError(Error):
  """Error raised if the dict cannot be deserialize from disk."""

class PersistentDict(dict):
  def __init__(self, path):
    super(PersistentDict, self).__init__()
    self._path = path
    self.update(self._read_from_disk())

  def _read_from_disk(self):
    try:
      return json.load(open(self._path))
    except IOError:
      # Coun't read file. Default to empty dict.
      return {}
    except ValueError:
      raise InvalidFileError

    if not isinstance(config, dict):
      raise InvalidFileError

  def _save_to_disk(self):
    with open(self._path, 'w') as handle:
      json.dump(self, handle, sort_keys=True, indent=2, separators=(',', ': '))

  def __delitem__(self, key):
    super(PersistentDict, self).__delitem__(key)
    self._save_to_disk()

  def __setitem__(self, key, value):
    super(PersistentDict, self).__setitem__(key, value)
    self._save_to_disk()

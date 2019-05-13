# dict implementation that automatically saves it's state to a file on disk.

import json
import os
from six import string_types

class Error(Exception):
  """Base class for all exception of this module."""

class InvalidFileError(Error):
  """Error raised if the dict cannot be deserialize from disk."""

class UnknownError(Error):
  """An unexpected error occurred."""

def _maybe_wrap(persistent_dict, item):
  if hasattr(item, '__iter__') and not isinstance(item, string_types):
    return PersistentDictWrapper(persistent_dict, item)
  else:
    return item

class PersistentDictWrapper(object):
  def __init__(self, persistent_dict, value):
    self._persistent_dict = persistent_dict
    self._value = value

  def __getattr__(self, name):
    attribute = self._value.__getattribute__(name)
    if hasattr(attribute, '__call__'):
      def wrapped_function(*args, **kwargs):
        result = attribute(*args, **kwargs)
        self._persistent_dict._save_to_disk()
        return _maybe_wrap(self._persistent_dict, result)
      return wrapped_function
    else:
      return _maybe_wrap(self._persistent_dict, attribute)

  def __delitem__(self, key):
    self._value.__delitem__(key)
    self._persistent_dict._save_to_disk()

  def __setitem__(self, key, value):
    self._value.__setitem__(key, value)
    self._persistent_dict._save_to_disk()

  def __getitem__(self, key):
    value = self._value.__getitem__(key)
    return _maybe_wrap(self._persistent_dict, value)

  def __len__(self):
    return self._value.__len__()

  def __contains__(self, item):
    return self._value.__contains__(item)

  def __iter__(self):
    return self._value.__iter__()


class PersistentDict(object):
  def __init__(self, path):
    self._path = path
    self._dict = self._read_from_disk()

  def _read_from_disk(self):
    try:
      with open(self._path) as f:
        return json.load(f)
    except IOError:
      # Coun't read file. Default to empty dict.
      return {}
    except ValueError:
      raise InvalidFileError

    raise UnknownError

  def _save_to_disk(self):
    if not self._dict:
      try:
        os.remove(self._path)
      except OSError:
        pass
      return
    with open(self._path, 'w') as handle:
      json.dump(self._dict, handle, sort_keys=True, indent=2,
                separators=(',', ': '))

  def __getattr__(self, name):
    attribute = self._dict.__getattribute__(name)
    if hasattr(attribute, '__call__'):
      def wrapped_function(*args, **kwargs):
        result = attribute(*args, **kwargs)
        self._save_to_disk()
        return _maybe_wrap(self, result)
      return wrapped_function
    else:
      return _maybe_wrap(self, attribute)

  def __delitem__(self, key):
    self._dict.__delitem__(key)
    self._save_to_disk()

  def __setitem__(self, key, value):
    self._dict.__setitem__(key, value)
    self._save_to_disk()

  def __getitem__(self, key):
    value = self._dict.__getitem__(key)
    return _maybe_wrap(self, value)

  def __len__(self):
    return self._dict.__len__()

  def __contains__(self, item):
    return self._dict.__contains__(item)

  def __iter__(self):
    return self._dict.__iter__()

  def __str__(self):
    return str(self._dict)

  def __repr__(self):
    return str(self._dict)

  def __eq__(self, other):
    return self._dict == other

  def __ne__(self, other):
    return self._dict != other

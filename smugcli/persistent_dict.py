"""`dict` automatically saving it's state to a file on disk."""

import json
import locale
import os
from typing import Generic, MutableMapping, MutableSequence, TypeVar, Union


class Error(Exception):
  """Base class for all exception of this module."""


class InvalidFileError(Error):
  """Error raised if the dict cannot be deserialize from disk."""


class UnknownError(Error):
  """An unexpected error occurred."""


WrappableTypes = Union[MutableSequence, MutableMapping]
NonWrappableTypes = Union[float, int, str]

WrappableTypeVar = TypeVar('WrappableTypeVar',
                           bound=WrappableTypes)
NonWrappableTypeVar = TypeVar('NonWrappableTypeVar',
                              bound=NonWrappableTypes)


def _maybe_wrap(
    persistent_dict: 'PersistentDict',
    item: Union[WrappableTypeVar, NonWrappableTypeVar]
) -> Union['_PersistentDictWrapper[WrappableTypeVar]', NonWrappableTypeVar]:
  if isinstance(item, (MutableSequence, MutableMapping)):
    return _PersistentDictWrapper(persistent_dict, item)
  return item


class _PersistentDictWrapper(Generic[WrappableTypeVar]):
  """Wraps objects held in PersistentDict propagating the auto-save logic."""

  def __init__(self,
               persistent_dict: 'PersistentDict',
               value: WrappableTypeVar) -> None:
    self._persistent_dict = persistent_dict
    self._value = value

  def __getattr__(self, name: str):
    attribute = self._value.__getattribute__(name)
    if hasattr(attribute, '__call__'):
      def wrapped_function(*args, **kwargs):
        result = attribute(*args, **kwargs)
        self._persistent_dict.save_to_disk()
        return _maybe_wrap(self._persistent_dict, result)
      return wrapped_function
    return _maybe_wrap(self._persistent_dict, attribute)

  def __delitem__(self, key):
    self._value.__delitem__(key)
    self._persistent_dict.save_to_disk()

  def __setitem__(self, key, value):
    self._value.__setitem__(key, value)
    self._persistent_dict.save_to_disk()

  def __getitem__(self, key):
    value = self._value.__getitem__(key)
    return _maybe_wrap(self._persistent_dict, value)

  def __len__(self):
    return self._value.__len__()

  def __contains__(self, item):
    return self._value.__contains__(item)

  def __iter__(self):
    return self._value.__iter__()


class PersistentDict():
  """`dict` that automatically saves its content to disk when updated."""

  def __init__(self, path: str):
    self._path = path
    self._dict = self._read_from_disk()

  def _read_from_disk(self):
    try:
      with open(self._path, encoding=locale.getpreferredencoding()) as file:
        return json.load(file)
    except IOError:
      # Couldn't read file. Default to empty dict.
      return {}
    except ValueError as exc:
      raise InvalidFileError('Invalid config file.') from exc
    except Exception as exc:
      raise UnknownError(
          'An unknown error occurred reading config file.') from exc

  def save_to_disk(self):
    """Save this `PersistentDict` to disk"""
    if not self._dict:
      try:
        os.remove(self._path)
      except OSError:
        pass
      return
    with open(self._path, 'w', encoding=locale.getpreferredencoding()) as file:
      json.dump(self._dict, file, sort_keys=True, indent=2,
                separators=(',', ': '))

  def __getattr__(self, name: str):
    attribute = self._dict.__getattribute__(name)
    if hasattr(attribute, '__call__'):
      def wrapped_function(*args, **kwargs):
        result = attribute(*args, **kwargs)
        self.save_to_disk()
        return _maybe_wrap(self, result)
      return wrapped_function
    return _maybe_wrap(self, attribute)

  def __delitem__(self, key):
    self._dict.__delitem__(key)
    self.save_to_disk()

  def __setitem__(self, key, value):
    self._dict.__setitem__(key, value)
    self.save_to_disk()

  def __getitem__(self, key: str):
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

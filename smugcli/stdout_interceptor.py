"""Context manager base class man-in-the-middling the global stdout."""

import sys


class Error(Exception):
  """Base class for all exception of this module."""


class InvalidUsageError(Error):
  """Error raised on incorrect API uses."""


class StdoutInterceptor():
  """Context manager base class man-in-the-middling the global stdout."""

  def __init__(self):
    self._original_stdout = None

  def __enter__(self) -> 'StdoutInterceptor':
    """Replaces global stdout and starts printing status after last write."""
    self._original_stdout = sys.stdout
    sys.stdout = self
    return self

  def __exit__(self, exc_type, exc_value, traceback) -> None:
    """Terminate this TaskManager and restore global stdout."""
    del exc_type, exc_value, traceback  # Unused.
    if self._original_stdout is None:
      raise InvalidUsageError(
          "Object must be used as a context manager, in a `with:` statement.")
    sys.stdout = self._original_stdout

  @property
  def stdout(self):
    """Returns the original stdout this class is replacing."""
    if self._original_stdout is None:
      raise InvalidUsageError(
          "Object must be used as a context manager, in a `with:` statement.")
    return self._original_stdout

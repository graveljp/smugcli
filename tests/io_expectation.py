"""Framework for setting Input and Output expectations in a unit test.

This file defines the class ExpectedInputOutput which can be used to override
sys.stdout to validate that expected outputs are printed and sys.stdin to
inject mock responses in the standard input. This is useful in unit test, to
validate that a command line tool behaves as expected.

The following example tests a program printing a few lines, asking a question
and acting according to the response:

  import io_expectation as expect

  mock_io = expect.ExpectedInputOutput()
  sys.stdin = mock_io
  sys.stdout = mock_io

  # Set expected I/Os.
  mock_io.set_expected_io(
    expect.InOrder(
      expect.Contains('initialization'),
      expect.Anything().repeatedly(),
      expect.Equals('Proceed?'),
      expect.Reply('yes'),
      expect.Prefix('Success')))

  # Run the program under test.
  print('Program initialization...')
  print('Loading resources...')
  print('Initialization complete.')
  print('Proceed? ')
  if raw_input() == 'yes':
    print('Success')
  else:
    print('Aborting')

  # Validate that the program matched all expectations.
  mock_io.assert_expectations_fulfilled()

Some expectation can be abbreviated, for instance, the following two
expectations are equivalent:
  io.set_expected_io(AnyOrder(Contains('foo'), Contains('bar')))
  io.set_expected_io(['foo', 'bar'])

If no inputs are expected, expectation can be specified after the fact, which
is usually more readable in unit tests. For instance:

  print('Some output text')
  mock_io.assert_output_was('Some output text')

  print('More output')
  print('Some more output')
  mock_io.assert_output_was(['More output', 'Some more output'])
"""

import copy
import difflib
import io
import re
import sys
from typing import Callable, Optional


def default_expectation(expected_io):
  """Defines the behavior of python standard types when used as expectation.

  This is used to allow syntactic sugar, where expectation can be specified
  using a lightweight syntax. For instance, the following two statement produce
  the same expectations:

  io.set_expected_io(AnyOrder(Contains('foo'), Contains('bar')))

  io.set_expected_io(['foo', 'bar'])

  Args:
    expected_io: python standard type

  Returns:
    ExpectBase subclass instance.
  """
  if isinstance(expected_io, (list, tuple)):
    return InOrder(*expected_io)
  if isinstance(expected_io, set):
    return AnyOrder(*expected_io)
  if isinstance(expected_io, str):
    return Contains(expected_io)
  return expected_io


class ExpectBase():
  """Base class for all expected response string matchers."""

  def __init__(self):
    self._consumed = False
    self._fulfilled = False
    self._saturated = False
    self._greedy = False
    self._thrifty = False

  @property
  def consumed(self) -> bool:
    """True when the expectation has been consumed."""
    return self._consumed

  @property
  def fulfilled(self) -> bool:
    """True when the expectation base condition has been met.
    The expectation could still accept more matches, until it's saturated.
    """
    return self._fulfilled

  @property
  def saturated(self) -> bool:
    """True when the expectation reached its upper limit of allowed matches."""
    return self._saturated

  @property
  def greedy(self) -> bool:
    """If True, repeated expectation will match as much as possible, possibly
    starving the following expectations."""
    return self._greedy

  @property
  def thrifty(self) -> bool:
    """If True, the expectation will only match if no other alternative
    expectations match."""
    return self._thrifty

  def consume(self, string: str) -> bool:
    """Matches a string against this expectation.

    Consumer expectation sub-classes must override this function.

    The expectation's internal states is updated accordingly. For instance,
    sequence expectations advances their state to the next expected IO.

    Args:
      str: the string to match against the expectation.

    Returns:
      bool: True if the string matched successfully."""
    del string  # Unused.
    self._consumed = True
    return False

  def test_consume(self, string: str) -> bool:
    """Tests if the expectation would success at consuming a string.

    Consumer expectation sub-classes must override this function.

    The internal state of the expectation are left untouched.

    Returns:
      bool: True if the string would match successfully.
    """
    del string  # Unused.
    return False

  def produce(self) -> Optional[str]:
    """Produces a string, as if entered by the user in response to a prompt.

    Producer expectation sub-classes must override this function.

    Returns:
      str, the string produced by the expectation.
    """
    return None

  def repeatedly(self,
                 min_repetition: int = 0,
                 max_repetition: Optional[int] = None) -> 'Repeatedly':
    """Shorthand for making this expectation repeat indefinitely.

    Returns:
      Repeatedly instance: wrapped version of self, which repeats 0 or more
          times.
    """
    return Repeatedly(self, min_repetition, max_repetition)

  def times(self,
            min_repetition: int = 0,
            max_repetition: Optional[int] = None) -> 'Repeatedly':
    """Shorthand for making this expectation repeat a given number of times.

    Args:
      min_repetition: int, the minimum number of times this expectation needs to
        match for it to be fulfilled.
      max_repetition: int, the number of repetition after which this expectation
        is saturated and won't successfully match another time.

    Returns:
      Repeatedly instance: wrapped version of self, which repeats from
      min_repetition to max_repetition times.
    """
    max_repetition = max_repetition or min_repetition
    return Repeatedly(self, min_repetition, max_repetition)

  def apply_transform(self, callback: Callable[[str], str]):
    """Apply a transformation on the expectation definition.

    The ExpectedInputOutput class calls this function on every expectations
    registered, which is useful for 'patching' all expectations with the same
    transformation. A common way to use this is to fix path delimiters to match
    the OS format in expectations containing paths.

    Args:
      callback: callback function to call to transform the expectation.
          Callback takes a string as input and returns a transforms version of
          that string.
    """
    del callback  # Unused.

  def description(self, saturated: bool) -> str:
    """Returns a textural description of this matcher."""
    del saturated  # Unused.
    raise NotImplementedError()

  def __and__(self, other: 'ExpectBase') -> 'And':
    ret = And(self, other)
    return ret

  def __or__(self, other: 'ExpectBase') -> 'Or':
    ret = Or(self, other)
    return ret


class ExpectStringBase(ExpectBase):
  """Base class for all string expectations."""

  def __init__(self, expected: str):
    super().__init__()
    self._expected = expected

  def consume(self, string: str) -> bool:
    self._consumed = True
    self._fulfilled = self._saturated = self.test_consume(string)
    return self._fulfilled

  def test_consume(self, string: str) -> bool:
    return self._match(string)

  def apply_transform(self, callback: Callable[[str], str]) -> None:
    self._expected = callback(self._expected)

  def _match(self, string: str) -> bool:
    del string  # Unused.
    raise NotImplementedError()

  def description(self, saturated: bool) -> str:
    del saturated  # Unused.
    name = type(self).__name__
    args = repr(self._expected)
    return f'{name}({args})'


class Equals(ExpectStringBase):
  """Matches a string equal to the specified string.

  Leading and trailing white-spaces are stripped.
  """

  def _match(self, string: str) -> bool:
    return string.strip() == self._expected.strip()


class Contains(ExpectStringBase):
  """Matches a string containing a specific sub-string."""

  def _match(self, string: str) -> bool:
    return self._expected in string


class Prefix(ExpectStringBase):
  """Matches a string having a specific prefix."""

  def _match(self, string: str) -> bool:
    return string.strip().startswith(self._expected)


class Regex(ExpectStringBase):
  """Matches a string using a regular expression."""

  def _match(self, string: str) -> bool:
    return re.match(self._expected, string, re.DOTALL) is not None


class Anything(ExpectBase):
  """Matches anything once."""

  def consume(self, string: str) -> bool:
    self._consumed = True
    self._fulfilled = self._saturated = self.test_consume(string)
    return True

  def test_consume(self, string: str) -> bool:
    del string  # Unused.
    return True

  def description(self, saturated: bool) -> str:
    del saturated  # Unused.
    return f'{type(self).__name__}()'


class And(ExpectBase):
  """Matcher succeeding when all its sub matcher succeed."""

  def __init__(self, *args):
    super().__init__()
    self._expected_list = [default_expectation(expected) for expected in args]

  @property
  def fulfilled(self) -> bool:
    return all(e.fulfilled for e in self._expected_list)

  @property
  def saturated(self) -> bool:
    return any(e.saturated for e in self._expected_list)

  def consume(self, string: str) -> bool:
    self._consumed = True
    return all(e.consume(string) for e in self._expected_list)

  def test_consume(self, string: str) -> bool:
    return all(e.test_consume(string) for e in self._expected_list)

  def apply_transform(self, callback: Callable[[str], str]) -> None:
    for expected in self._expected_list:
      expected.apply_transform(callback)

  def description(self, saturated: bool) -> str:
    parts = [a.description(saturated) for a in self._expected_list
             if not a.consumed or a.saturated == saturated]
    if len(parts) == 1:
      return parts[0]
    return ' and '.join(parts)


class Or(ExpectBase):
  """Matcher succeeding when one of its sub matcher succeed."""

  def __init__(self, *args):
    super().__init__()
    self._expected_list = [default_expectation(expected) for expected in args]

  @property
  def fulfilled(self):
    return any(e.fulfilled for e in self._expected_list)

  @property
  def saturated(self):
    return all(e.saturated for e in self._expected_list)

  def consume(self, string):
    self._consumed = True
    return any(e.consume(string) for e in self._expected_list)

  def test_consume(self, string):
    return any(e.test_consume(string) for e in self._expected_list)

  def apply_transform(self, callback: Callable[[str], str]):
    for expected in self._expected_list:
      expected.apply_transform(callback)

  def description(self, saturated):
    parts = [a.description(saturated) for a in self._expected_list
             if not a.consumed or a.saturated == saturated]
    if len(parts) == 1:
      return parts[0]
    return ' or '.join(parts)


class Not(ExpectBase):
  """Matcher succeeding when it's sub-matcher fails."""

  def __init__(self, expected):
    super().__init__()
    self._expected = expected
    self._thrifty = True

  def consume(self, string):
    self._consumed = True
    self._fulfilled = not self._expected.consume(string)
    self._saturated = not self._expected.saturated
    return self._fulfilled

  def test_consume(self, string):
    return not self._expected.test_consume(string)

  def apply_transform(self, callback: Callable[[str], str]):
    self._expected.apply_transform(callback)

  def description(self, saturated):
    return f'Not({self._expected.description(not saturated)})'


class Repeatedly(ExpectBase):
  """Wraps an expectation to make it repeat a given number of times."""

  def __init__(self, sub_expectation, min_repetition=0, max_repetition=None):
    super().__init__()
    self._min_repetition = min_repetition
    self._max_repetition = max_repetition
    self._sub_expectation = default_expectation(sub_expectation)
    self._current_repetition = 0
    self._current_expectation = copy.deepcopy(self._sub_expectation)
    self._thrifty = self._sub_expectation.thrifty

  @property
  def fulfilled(self):
    return self._current_repetition >= self._min_repetition

  @property
  def saturated(self):
    return (self._max_repetition is not None and
            self._current_repetition >= self._max_repetition)

  def consume(self, string):
    self._consumed = True
    result = self._current_expectation.consume(string)
    if self._current_expectation.fulfilled:
      self._current_repetition += 1
      self._current_expectation = copy.deepcopy(self._sub_expectation)
    return result

  def test_consume(self, string):
    return self._current_expectation.test_consume(string)

  def produce(self):
    result = self._current_expectation.produce()
    if self._current_expectation.saturated:
      self._current_repetition += 1
      self._current_expectation = copy.deepcopy(self._sub_expectation)
    return result

  def apply_transform(self, callback: Callable[[str], str]):
    self._sub_expectation.apply_transform(callback)

  def description(self, saturated):
    arg1 = max(self._min_repetition - self._current_repetition, 0)
    arg2 = (self._max_repetition - self._current_repetition
            if self._max_repetition is not None else None)
    name = type(self).__name__
    desc = self._current_expectation.description(saturated)
    arg1_str = f', {arg1}' if arg1 > 0 or arg2 is not None else ''
    arg2_str = f', {arg2}' if arg2 else ''
    return f'{name}({desc}{arg1_str}{arg2_str})'


class ExpectSequenceBase(ExpectBase):
  """Base class for all sequence-based expectations."""

  def __init__(self, *args):
    super().__init__()
    self._expected_list = [default_expectation(expected) for expected in args]

  @property
  def fulfilled(self):
    return all(e.fulfilled for e in self._expected_list)

  @property
  def saturated(self):
    return all(e.saturated for e in self._expected_list)

  def apply_transform(self, callback: Callable[[str], str]):
    for expected in self._expected_list:
      expected.apply_transform(callback)

  def description(self, saturated):
    parts = [a.description(saturated) for a in self._expected_list
             if not a.consumed or a.saturated == saturated]
    if len(parts) == 1:
      return parts[0]
    name = type(self).__name__
    args = ', '.join(parts)
    return f'{name}({args})'


class InOrder(ExpectSequenceBase):
  """Sequence of expectations that must match in right order."""

  def consume(self, string):
    self._consumed = True
    to_consume = None
    for i, expected in enumerate(self._expected_list):
      matches = expected.test_consume(string)
      if matches:
        to_consume = (i, expected)
        if expected.greedy or not expected.fulfilled:
          break

      elif expected.fulfilled:
        continue

      else:
        break

    if to_consume is not None:
      i, expected = to_consume
      consumed = expected.consume(string)
      assert consumed
      # We got a match somewhere down the sequence. Discard any preceding
      # fulfilled expectations.
      self._expected_list = self._expected_list[i:]
      if expected.saturated:
        self._expected_list.remove(expected)
      return consumed

    return False

  def test_consume(self, string):
    for expected in self._expected_list:
      if expected.test_consume(string):
        return True
      if not expected.fulfilled:
        return False
    return False

  def produce(self):
    for i, expected in enumerate(self._expected_list):
      result = expected.produce()
      if result:
        # We got a match somewhere down the sequence. Discard any preceding
        # fulfilled expectations.
        self._expected_list = self._expected_list[i:]
        if expected.saturated:
          self._expected_list.remove(expected)
        return result
      if not expected.fulfilled:
        return None
    return None


class AnyOrder(ExpectSequenceBase):
  """Sequence of expectation that can match in any order."""

  def consume(self, string):
    self._consumed = True
    to_consume = None
    for expected in self._expected_list:
      if expected.test_consume(string):
        to_consume = expected
        if not expected.thrifty and (expected.greedy or not expected.fulfilled):
          break

    if to_consume is not None:
      consumed = to_consume.consume(string)
      assert consumed
      if to_consume.saturated:
        self._expected_list.remove(to_consume)
      return True

    return False

  def test_consume(self, string):
    return any(expected.test_consume(string)
               for expected in self._expected_list)

  def produce(self):
    for expected in self._expected_list:
      result = expected.produce()
      if result:
        if expected.saturated:
          self._expected_list.remove(expected)
        return result
    return None


def Somewhere(expectation):  # pylint: disable=invalid-name
  """Match an expectation anywhere in a document."""
  return InOrder(Anything().repeatedly(),
                 expectation,
                 Anything().repeatedly())


class Url(ExpectBase):
  """Matches a URL. This matcher won't replace '/' to '\' on Windows."""

  def __init__(self, sub_expectation):
    super().__init__()
    self._expected = default_expectation(sub_expectation)

  def consume(self, string):
    self._consumed = True
    self._fulfilled = self._expected.consume(string)
    self._saturated = self._expected.saturated
    return self._fulfilled

  def test_consume(self, string):
    return self._expected.test_consume(string)

  def apply_transform(self, callback: Callable[[str], str]) -> None:
    del callback  # Unused.

  def description(self, saturated):
    return f'Url({self._expected.description(saturated)})'


class Reply(ExpectBase):
  """Expects a read to the input pipe and replies with a specific string."""

  def __init__(self, reply_string):
    super().__init__()
    self._reply_string = reply_string

  def produce(self):
    self._fulfilled = self._saturated = True
    return self._reply_string

  def _consume(self, line):
    raise AssertionError(f'Expecting user input but got output line: {line}')

  def description(self, saturated):
    name = type(self).__name__
    args = self._reply_string
    return f'{name}({args})'


class ExpectedInputOutput():
  """File object for overriding stdin/out, mocking inputs & checking outputs."""

  def __init__(self):
    self.set_transform_fn(None)
    self.set_expected_io(None)
    self._original_stdin = sys.stdin
    self._original_stdout = sys.stdout
    self._expected_io = None
    self._cmd_output = io.StringIO()

  def close(self) -> None:
    """Close this object and restore global io streams."""
    sys.stdin = self._original_stdin
    sys.stdout = self._original_stdout
    self._expected_io = None
    self._cmd_output = io.StringIO()

  def set_transform_fn(self, transform_fn: Optional[Callable[[str], str]]):
    """Callback to transform all expectations passed in set_expected_io.

    Useful for 'patching' all expectations with the same transformation. A
    common way to use this is to fix path delimiters to match the OS format in
    expectations containing paths.

    Args:
      transform_fn: callback function to call to transform the expectation.
          Callback takes a string as input and returns a transforms version of
          that string.
    """
    self._transform_fn = transform_fn

  def set_expected_io(self, expected_io):
    """Set an expectation for the next sequence of IOs.

    The expected IO can be specified as an instance of an ExpectBase child
    class, or as a python standard type (str, list, etc.) which are mapped to
    an expectation object using default_expectation.

    If expected_io is None, next IOs will be ignored.

    Args:
      expected_io: instance of an ExpectBase subclass or any types accepted by
          default_expectation, the expectation to apply all input and outputs
          against.
    """
    self._expected_io = self._patch_expected_io(expected_io)
    self._cmd_output = io.StringIO()

  def write(self, string):
    """File object 'write' method, matched against the next expected output.

    Args:
      string: str, string being written to stdout.
    """
    self._original_stdout.write(string)
    self._cmd_output.write(string)

  def flush(self):
    """File object 'flush' method."""
    self._original_stdout.flush()

  def readline(self):
    """File object 'readline' method, replied using the next expected input.

    Returns:
      str, the mock string faking a read from stdin.

    Raises:
      AssertionError: raised when IOs do not match expectations.
    """
    if self._expected_io is None:
      raise AssertionError('Trying to readline but no expected IO was set.')

    self._match_pending_outputs()
    if self._expected_io.saturated:
      raise AssertionError('No more user input prompt expected')
    reply = self._expected_io.produce()
    if not reply:
      raise AssertionError(
          'Unexpected user input prompt request. Expected:\n' +
          self._expected_io.description(saturated=False))
    reply += '\n'
    self._original_stdout.write(reply)
    return reply

  def assert_expectations_fulfilled(self) -> io.StringIO:
    """Asserts that all expectation are fulfilled.

    Resets this object, ready to restart with a new set_expected_io.

    Raises:
      AssertionError: raised when IOs do not match expectations.
    """
    cmd_output = self._cmd_output
    self._match_pending_outputs()
    if self._expected_io:
      if not self._expected_io.fulfilled:
        raise AssertionError('Pending IO expectation never fulfilled:\n' +
                             self._expected_io.description(saturated=False))

    self.set_expected_io(None)
    return cmd_output

  def assert_output_was(self, expected_output):
    """Asserts that the previous outputs matched the specified expectation.

    Args:
      expected_output: instance of an ExpectBase subclass, the expectation to
          apply all previous outputs against.

    Raises:
      AssertionError: raised when previous outputs do not match expectations.
    """
    self._expected_io = self._patch_expected_io(expected_output)
    self.assert_expectations_fulfilled()

  def _patch_expected_io(self, expected_io):
    """Patch the specified expectation, applying defaults and transforms.

    Args:
      expected_io: instance of an ExpectBase subclass or any types accepted by
          default_expectation.

    Returns:
      Instance of an ExpectBase subclass.
    """
    patched_expected_io = default_expectation(expected_io)

    if patched_expected_io and self._transform_fn:
      patched_expected_io.apply_transform(self._transform_fn)

    return patched_expected_io

  def _match_pending_outputs(self):
    """Match any pending IO against the expectations.

    Raises:
      AssertionError: raised when IOs do not match expectations.
    """
    output_lines = self._cmd_output.getvalue().splitlines(True)
    self._cmd_output = io.StringIO()

    if self._expected_io:
      for line in output_lines:
        if self._expected_io.saturated:
          raise AssertionError(f'No more output expected, but got: \'{line}\'')
        if not self._expected_io.consume(line):
          raise AssertionError(
              'Unexpected output:\n'
              '%s' % '\n'.join(difflib.ndiff(
                  self._expected_io.description(
                      saturated=False).splitlines(True),
                  repr(line).splitlines(True))))

# Framework for setting Input and Output expectations in a unit test.
#
# This file defines the class ExpectedInputOutput which can be used to override
# sys.stdout to validate that expected outputs are printed and sys.stdin to
# inject mock responses in the standard input. This is useful in unit test, to
# validate that a command line tool behaves as expected.
#
# The following example tests a program printing a few lines, asking a question
# and acting according to the response:
#
#   import io_expectation as expect
#
#   mock_io = expect.ExpectedInputOutput()
#   sys.stdin = mock_io
#   sys.stdout = mock_io
#
#   # Set expected I/Os.
#   mock_io.set_expected_io(
#     expect.InOrder(
#       expect.Contains('initialization'),
#       expect.Anything().repeatedly(),
#       expect.Equals('Proceed?'),
#       expect.Reply('yes'),
#       expect.Prefix('Success')))
#
#   # Run the program under test.
#   print('Program initialization...')
#   print('Loading resources...')
#   print('Initialization complete.')
#   print('Proceed? ')
#   if raw_input() == 'yes':
#     print('Success')
#   else:
#     print('Aborting')
#
#   # Validate that the program matched all expectations.
#   mock_io.assert_expectations_fulfilled()
#
# Some expectation can be abbreviated, for insatnce, the following two
# expectations are equivalent:
#   io.set_expected_io(AnyOrder(Contains('foo'), Contains('bar')))
#   io.set_expected_io(['foo', 'bar'])
#
# If no inputs are expected, expectation can be specified after the fact, which
# is usually more readable in unit tests. For instance:
#
#   print('Some output text')
#   mock_io.assert_output_was('Some output text')
#
#   print('More output')
#   print('Some more output')
#   mock_io.assert_output_was(['More output', 'Some more output'])


import copy
import difflib
import re
import six
import sys


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
  elif isinstance(expected_io, set):
    return AnyOrder(*expected_io)
  elif isinstance(expected_io, six.string_types):
    return Contains(expected_io)
  else:
    return expected_io


class ExpectBase(object):
  """Base class for all expected response string matchers."""

  def __init__(self):
    self._fulfilled = False
    self._saturated = False
    self._greedy = False

  @property
  def fulfilled(self):
    """True when the expectation base condition has been met.
    The expectation could still accept more matches, until it's saturated.
    """
    return self._fulfilled

  @property
  def saturated(self):
    """True when the expectation reached it's upper limit of allowed matches."""
    return self._saturated

  @property
  def greedy(self):
    """If True, repeated expectation will match as much as possible, possibly
    starving the following expectations."""
    return self._greedy

  def consume(self, string):
    """Matches a string against this expectation.

    Consumer expectation sub-classes must override this function.

    The expectation's internal states is updated accordingly. For instance,
    sequence expectations advances their state to the next expected IO.

    Args:
      str: the string to match against the expectation.

    Returns:
      bool: True if the string matched successfully."""
    return False

  def test_consume(self, string):
    """Tests if the expectation would success at consuming a string.

    Consumer expectation sub-classes must override this function.

    The internal state of the expectation are left untouched.

    Returns:
      bool: True if the string would match successfully.
    """
    return False

  def produce(self):
    """Produces a string, as if entered by the user in response to a prompt.

    Producer expectation sub-classes must override this function.

    Returns:
      str, the string produced by the expectation.
    """
    return None

  def repeatedly(self):
    """Shorthand for making this expectation repeat indefinitely.

    Returns:
      Repeatedly instance: wrapped version of self, which repeats 0 or more
          times.
    """
    return Repeatedly(self)

  def times(self, min_repetition, max_repetition=None):
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

  def apply_transform(self, fn):
    """Apply a transformation on the expectation definition.

    The ExpectedInputOutput class calls this function on every expectations
    registered, which is useful for 'patching' all expectations with the same
    transformation. A common way to use this is to fix path delimiters to match
    the OS format in expectations containing paths.

    Args:
      fn: callback function to call to transform the expectation. Callback
          takes a string as input and returns a transforms version of that
          string.
    """
    pass


class ExpectStringBase(ExpectBase):

  def __init__(self, expected):
    super(ExpectStringBase, self).__init__()
    self._expected = expected

  def consume(self, string):
    self._fulfilled = self._saturated = self.test_consume(string)
    return self._fulfilled

  def test_consume(self, string):
    return self._match(string)

  def apply_transform(self, fn):
    self._expected = fn(self._expected)

  def _match(self, string):
    raise NotImplementedError()

  def __repr__(self):
    return '%s(%s)' % (type(self).__name__, repr(self._expected))

class Equals(ExpectStringBase):
  """Matches a string equal to the specified string.

  Leading and trailing white-spaces are stripped.
  """

  def _match(self, string):
    return string.strip() == self._expected.strip()


class Contains(ExpectStringBase):
  """Matches a string containing a specific sub-string."""

  def _match(self, string):
    return self._expected in string


class Prefix(ExpectStringBase):
  """Matches a string having a specific prefix."""

  def _match(self, string):
    return string.strip().startswith(self._expected)


class Regex(ExpectStringBase):
  """Matches a string using a regular expression."""

  def _match(self, other):
    return re.match(self._expected, other, re.DOTALL)


class Anything(ExpectBase):
  """Matches anything once."""

  def consume(self, string):
    self._fulfilled = self._saturated = self.test_consume(string)
    return True

  def test_consume(self, string):
    return True

  def __repr__(self):
    return '%s()' % type(self).__name__


class Repeatedly(ExpectBase):
  """Wraps an expectation to make it repeat a given number of times."""

  def __init__(self, sub_expectation, min_repetition=0, max_repetition=None):
    super(Repeatedly, self).__init__()
    self._min_repetition = min_repetition
    self._max_repetition = max_repetition
    self._sub_expectation = default_expectation(sub_expectation)
    self._current_repetition = 0
    self._current_expectation = copy.deepcopy(self._sub_expectation)

  @property
  def fulfilled(self):
    return self._current_repetition >= self._min_repetition

  @property
  def saturated(self):
    return (self._max_repetition is not None and
            self._current_repetition >= self._max_repetition)

  def consume(self, string):
    result = self._current_expectation.consume(string)
    if self._current_expectation.saturated:
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

  def apply_transform(self, fn):
    self._sub_expectation.apply_transform(fn)

  def __repr__(self):
    arg1 = max(self._min_repetition - self._current_repetition, 0)
    arg2 = (self._max_repetition - self._current_repetition
            if self._max_repetition is not None else None)
    return '%s(%s%s%s)' % (
      type(self).__name__, repr(self._sub_expectation),
      ', %d' % arg1 if arg1 > 0 or arg2 is not None else '',
      ', %d' % arg2 if arg2 else '')


class ExpectSequenceBase(ExpectBase):
  """Base class for all sequence-based expectations."""

  def __init__(self, *args):
    super(ExpectSequenceBase, self).__init__()
    self._expected_list = [default_expectation(expected) for expected in args]

  @property
  def fulfilled(self):
    return all(e.fulfilled for e in self._expected_list)

  @property
  def saturated(self):
    return all(e.saturated for e in self._expected_list)

  def apply_transform(self, fn):
    for expected in self._expected_list:
      expected.apply_transform(fn)

  def __repr__(self):
    unfulfilled = [repr(a) for a in self._expected_list if not a.fulfilled]
    if len(unfulfilled) == 1:
      return unfulfilled[0]
    else:
      return '%s(%s)' % (type(self).__name__, ', '.join(unfulfilled))


class InOrder(ExpectSequenceBase):
  """Sequence of expectations that must match in right order."""

  def consume(self, string):
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
      assert(consumed)
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
      elif not expected.fulfilled:
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
      elif not expected.fulfilled:
        return None
    return None


class AnyOrder(ExpectSequenceBase):
  """Sequence of expectation that can match in any order."""

  def consume(self, string):
    to_consume = None
    for expected in self._expected_list:
      if expected.test_consume(string):
        to_consume = expected
        if expected.greedy or not expected.fulfilled:
          break

    if to_consume is not None:
      consumed = to_consume.consume(string)
      assert(consumed)
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


def Somewhere(expectation):
  """Match an expectation anywhere in a document."""
  return InOrder(Anything().repeatedly(),
                 expectation,
                 Anything().repeatedly())


class Reply(ExpectBase):
  """Expects a read to the input pipe and replies with a specific string."""

  def __init__(self, reply_string):
    super(Reply, self).__init__()
    self._reply_string = reply_string

  def produce(self):
    self._fulfilled = self._saturated = True
    return self._reply_string

  def _consume(self, line):
    raise AssertionError('Expecting user input but got output line: %s' % line)

  def __repr__(self):
    return '%s(%s)' % (type(self).__name__, self._reply_string)


class ExpectedInputOutput(object):
  """File object for overriding stdin/out, mocking inputs & checking outputs."""

  def __init__(self):
    self.set_transform_fn(None)
    self.set_expected_io(None)
    self._original_stdin = sys.stdin
    self._original_stdout = sys.stdout

  def set_transform_fn(self, transform_fn):
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
    self._cmd_output = six.StringIO()

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
      raise AssertionError('Unexpected user input prompt request. Expected:\n'
                           '%s' % repr(self._expected_io))
    reply += '\n'
    self._original_stdout.write(reply)
    return reply

  def assert_expectations_fulfilled(self):
    """Asserts that all expectation are fulfilled.

    Resets this object, ready to restart with a new set_expected_io.

    Raises:
      AssertionError: raised when IOs do not match expectations.
    """
    self._match_pending_outputs()
    if self._expected_io:
      if not self._expected_io.fulfilled:
        raise AssertionError('Pending IO expectation never fulfulled:\n%s' %
                             repr(self._expected_io))

    self.set_expected_io(None)

  def assert_output_was(self, expected_output):
    """Asserts that the previous outputs matche the specified expectation.

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
    self._cmd_output = six.StringIO()

    if self._expected_io:
      for line in output_lines:
        if self._expected_io.saturated:
          raise AssertionError('No more output expected, but got: \'%s\'' %
                               line)
        if not self._expected_io.consume(line):
          raise AssertionError('Unexpected output:\n'
                               '%s' % '\n'.join(difflib.ndiff(
                                 repr(self._expected_io).splitlines(True),
                                 repr(line).splitlines(True))))

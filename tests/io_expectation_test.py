from __future__ import print_function

import io_expectation as expect

from parameterized import parameterized, param
from six.moves import input
import sys
import unittest
import re

def AssertEquals(lhs, rhs):
  if lhs != rhs:
    raise AssertionError('Strings are not equals: %s != %s' % (lhs, rhs))


class IoExpectationTest(unittest.TestCase):

  def setUp(self):
    self._io = expect.ExpectedInputOutput()
    sys.stdin = self._io
    sys.stdout = self._io

  def tearDown(self):
    sys.stdin = self._io._original_stdin
    sys.stdout = self._io._original_stdout

  @parameterized.expand([
    # ==== expect.Equals ====
    param(
      'expect_equals',
      expected_io=expect.Equals('Expected output\n'),
      ios=lambda: print('Expected output'),
      error_message=None),

    param(
      'expect_equals_missing_newline',
      expected_io=expect.Equals('\nExpected output\n'),
      ios=lambda: sys.stdout.write('Expected output'),
      error_message=None),

    param(
      'expect_equals_missing_white_space',
      expected_io=expect.Equals(' Expected output '),
      ios=lambda: print('Expected output'),
      error_message=None),

    param(
      'expect_equals_extra_white_space_and_newlines',
      expected_io=expect.Equals('Expected output'),
      ios=lambda: print(' Expected output '),
      error_message=None),

    param(
      'expect_equals_no_output',
      expected_io=expect.Equals('Expected output'),
      ios=lambda: None,
      error_message=("Pending IO expectation never fulfulled:\n"
                     "Equals('Expected output')")),

    param(
      'expect_equals_mismatch',
      expected_io=expect.Equals('Expected output'),
      ios=lambda: (print('An Expected output and some more'),
                   print('Some more other output')),
      error_message=("Unexpected output:\n"
                     "- Equals('Expected output')\n"
                     "+ 'An Expected output and some more\\n'")),

    param(
      'expect_equals_extra_output',
      expected_io=expect.Equals('Expected output'),
      ios=lambda: (print('Expected output'),
                   print('Unexpected output')),
      error_message="No more output expected, but got: 'Unexpected output\n'"),

    # ==== expect.Contains ====
    param(
      'expect_contains',
      expected_io=expect.Contains('out'),
      ios=lambda: print('Some output'),
      error_message=None),

    param(
      'expect_contains_no_output',
      expected_io=expect.Contains('out'),
      ios=lambda: None,
      error_message=("Pending IO expectation never fulfulled:\n"
                     "Contains('out')")),

    param(
      'expect_contains_mismatch',
      expected_io=expect.Contains('out'),
      ios=lambda: print('Something else'),
      error_message=("Unexpected output:\n"
                     "- Contains('out')\n"
                     "+ 'Something else\\n'")),

    param(
      'expect_contains_extra_output',
      expected_io=expect.Contains('out'),
      ios=lambda: (print('Some output'),
                   print('Unexpected output')),
      error_message="No more output expected, but got: 'Unexpected output\n'"),


    # ==== expect.Prefix ====
    param(
      'expect_prefix',
      expected_io=expect.Prefix('Expected'),
      ios=lambda: print('Expected output'),
      error_message=None),

    param(
      'expect_prefix_extra_whitespace',
      expected_io=expect.Prefix('Expected'),
      ios=lambda: print('  Expected output'),
      error_message=None),

    param(
      'expect_prefix_no_output',
      expected_io=expect.Prefix('Expected'),
      ios=lambda: None,
      error_message=("Pending IO expectation never fulfulled:\n"
                     "Prefix('Expected')")),

    param(
      'expect_prefix_mismatch',
      expected_io=expect.Prefix('Expected'),
      ios=lambda: print('Something else'),
      error_message=("Unexpected output:\n"
                     "- Prefix('Expected')\n"
                     "+ 'Something else\\n'")),

    param(
      'expect_prefix_extra_output',
      expected_io=expect.Prefix('Expected'),
      ios=lambda: (print('Expected output'),
                   print('Unexpected output')),
      error_message="No more output expected, but got: 'Unexpected output\n'"),

    # ==== expect.Regex ====
    param(
      'expect_regex',
      expected_io=expect.Regex('.xpec.*d.*'),
      ios=lambda: print('Expected output'),
      error_message=None),

    param(
      'expect_regex_no_output',
      expected_io=expect.Regex('.xpec.*d.*'),
      ios=lambda: None,
      error_message=("Pending IO expectation never fulfulled:\n"
                     "Regex('.xpec.*d.*')")),

    param(
      'expect_regex_mismatch',
      expected_io=expect.Regex('Expec.*d'),
      ios=lambda: print('Something else'),
      error_message=("Unexpected output:\n"
                     "- Regex('Expec.*d')\n"
                     "+ 'Something else\\n'")),

    param(
      'expect_regex_extra_output',
      expected_io=expect.Regex('.*xpec.*d.*'),
      ios=lambda: (print('Expected output'),
                   print('Unexpected output')),
      error_message="No more output expected, but got: 'Unexpected output\n'"),

    # ==== expect.Anything ====
    param(
      'expect_anyting_success',
      expected_io=expect.Anything(),
      ios=lambda: print('Some output'),
      error_message=None),

    param(
      'expect_anyting_no_output',
      expected_io=expect.Anything(),
      ios=lambda: None,
      error_message=("Pending IO expectation never fulfulled:\n"
                     "Anything()")),

    param(
      'expect_anyting_extra_output',
      expected_io=expect.Anything(),
      ios=lambda: (print('Some output'),
                   print('Some more output')),
      error_message="No more output expected, but got: 'Some more output\n'"),

    # ==== Repeatedly ====
    param(
      'expect_repeatedly_equals_at_min',
      expected_io=expect.Repeatedly(expect.Equals('Expected output'), 2, 4),
      ios=lambda: (print('Expected output'),
                   print('Expected output')),
      error_message=None),

    param(
      'expect_repeatedly_equals_in_range',
      expected_io=expect.Repeatedly(expect.Equals('Expected output'), 2, 4),
      ios=lambda: (print('Expected output'),
                   print('Expected output'),
                   print('Expected output')),
      error_message=None),

    param(
      'expect_repeatedly_equals_at_max',
      expected_io=expect.Repeatedly(expect.Equals('Expected output'), 2, 4),
      ios=lambda: (print('Expected output'),
                   print('Expected output'),
                   print('Expected output'),
                   print('Expected output')),
      error_message=None),

    param(
      'expect_repeatedly_equals_no_input',
      expected_io=expect.Repeatedly(expect.Equals('Expected output'), 2, 4),
      ios=lambda: None,
      error_message=("Pending IO expectation never fulfulled:\n"
                     "Repeatedly(Equals('Expected output'), 2, 4)")),

    param(
      'expect_repeatedly_equals_below_min',
      expected_io=expect.Repeatedly(expect.Equals('Expected output'), 2, 4),
      ios=lambda: print('Expected output'),
      error_message=("Pending IO expectation never fulfulled:\n"
                     "Repeatedly(Equals('Expected output'), 1, 3)")),

    param(
      'expect_repeatedly_equals_above_max',
      expected_io=expect.Repeatedly(expect.Equals('Expected output'), 2, 4),
      ios=lambda: (print('Expected output'),
                   print('Expected output'),
                   print('Expected output'),
                   print('Expected output'),
                   print('Expected output')),
      error_message="No more output expected, but got: 'Expected output\n'"),

    param(
      'expect_repeatedly_equals_mismatch',
      expected_io=expect.Repeatedly(expect.Equals('Expected output'), 2, 4),
      ios=lambda: (print('Expected output'),
                   print('Expected output'),
                   print('Some other output')),
      error_message=("Unexpected output:\n"
                     "- Repeatedly(Equals('Expected output'), 0, 2)\n"
                     "+ 'Some other output\\n'")),

    param(
      'short_syntax_expect_indefinitely_repeating_error',
      expected_io=expect.Repeatedly(['a', 'b']),
      ios=lambda: (print('a'),
                   print('b'),
                   print('b'),
                   print('a')),
      error_message=("Unexpected output:\n"
                     "- Repeatedly(InOrder(Contains('a'), Contains('b')))\n"
                     "+ 'b\\n'")),


    # ==== InOrder ====
    param(
      'expect_in_order_equals',
      expected_io=expect.InOrder(expect.Equals('First expected output'),
                                 expect.Equals('Second expected output'),
                                 expect.Equals('Third expected output')),
      ios=lambda: (print('First expected output'),
                   print('Second expected output'),
                   print('Third expected output')),
      error_message=None),

    param(
      'expect_in_order_equals_mismatch',
      expected_io=expect.InOrder(expect.Equals('First expected output'),
                                 expect.Equals('Second expected output'),
                                 expect.Equals('Third expected output')),
      ios=lambda: (print('First expected output'),
                   print('Third expected output')),
      error_message=("Unexpected output:\n"
                     "- InOrder(Equals('Second expected output'), "
                               "Equals('Third expected output'))\n"
                     "+ 'Third expected output\\n'")),

    param(
      'expect_in_order_equals_extra_output',
      expected_io=expect.InOrder(expect.Equals('First expected output'),
                                 expect.Equals('Second expected output')),
      ios=lambda: (print('First expected output'),
                   print('Second expected output'),
                   print('Unexpected output')),
      error_message="No more output expected, but got: 'Unexpected output\n'"),

    param(
      'expect_in_order_repeatedly',
      expected_io=expect.InOrder(expect.Equals('Repeated output').times(2, 4),
                                 expect.Equals('Remaining output')),
      ios=lambda: (print('Repeated output'),
                   print('Repeated output'),
                   print('Repeated output'),
                   print('Remaining output')),
      error_message=None),

    param(
      'expect_any_order_of_in_orders_1',
      expected_io=(
        expect.AnyOrder(
          expect.InOrder('In order 1-a', 'In order 1-b'),
          expect.InOrder('In order 2-a', 'In order 2-b'))),
      ios=lambda: (print('In order 1-a'),
                   print('In order 1-b'),
                   print('In order 2-a'),
                   print('In order 2-b')),
      error_message=None),

    param(
      'expect_any_order_of_in_orders_2',
      expected_io=(
        expect.AnyOrder(
          expect.InOrder('In order 1-a', 'In order 1-b'),
          expect.InOrder('In order 2-a', 'In order 2-b'))),
      ios=lambda: (print('In order 1-a'),
                   print('In order 2-a'),
                   print('In order 2-b'),
                   print('In order 1-b')),
      error_message=None),

    param(
      'expect_any_order_of_in_orders_error',
      expected_io=(
        expect.AnyOrder(
          expect.InOrder('In order 1-a', 'In order 1-b'),
          expect.InOrder('In order 2-a', 'In order 2-b'))),
      ios=lambda: (print('In order 1-a'),
                   print('In order 2-b'),
                   print('In order 2-a'),
                   print('In order 1-b')),
      error_message=("Unexpected output:\n"
                     "- AnyOrder(Contains('In order 1-b'), "
                                "InOrder(Contains('In order 2-a'), "
                                        "Contains('In order 2-b')))\n"
                     "+ 'In order 2-b\\n'")),

    param(
      'expect_in_order_of_contains_and_anything',
      expected_io=(
        expect.AnyOrder(
          expect.Contains('foo'),
          expect.Contains('bar'),
          expect.Anything().repeatedly())),
      ios=lambda: (print('Second match is "foo".'),
                   print('First match is "bar".'),
                   print('Some more output.')),
      error_message=None),

    param(
      'expect_in_order_of_anything_and_contains',
      expected_io=(
        expect.InOrder(
          expect.Anything().repeatedly(),
          expect.Contains('foo'),
          expect.Contains('bar'),
          expect.Anything().repeatedly())),
      ios=lambda: (print('Some output'),
                   print('Second match is "foo".'),
                   print('First match is "bar".'),
                   print('Some more output.')),
      error_message=None),

    # ==== AnyOrder ====
    param(
      'expect_any_order_equals',
      expected_io=expect.AnyOrder(expect.Equals('First expected output'),
                                  expect.Equals('Second expected output'),
                                  expect.Equals('Third expected output')),
      ios=lambda: (print('Second expected output'),
                   print('First expected output'),
                   print('Third expected output')),
      error_message=None),

    param(
      'expect_any_order_or_in_order_repetitions',
      expected_io=(
        expect.AnyOrder(
          expect.InOrder(
            expect.Equals('Repeated output').times(2,4),
            expect.Equals('Last in order')),
          expect.Equals('At any time'))),
      ios=lambda: (print('Repeated output'),
                   print('Repeated output'),
                   print('Repeated output'),
                   print('At any time'),
                   print('Repeated output'),
                   print('Last in order')),
      error_message=None),

    param(
      'expect_any_order_of_contains_and_anything',
      expected_io=(
        expect.AnyOrder(
          expect.Contains('foo'),
          expect.Contains('bar'),
          expect.Anything().repeatedly())),
      ios=lambda: (print('Something'),
                   print('First match is "bar".'),
                   print('Something else'),
                   print('Second match is "foo".'),
                   print('Some more output.')),
      error_message=None),

    param(
      'expect_any_order_of_anything_and_contains',
      expected_io=(
        expect.AnyOrder(
          expect.Anything().repeatedly(),
          expect.Contains('foo'),
          expect.Contains('bar'))),
      ios=lambda: (print('Something'),
                   print('First match is "bar".'),
                   print('Something else'),
                   print('Second match is "foo".'),
                   print('Some more output.')),
      error_message=None),

    # ==== Reply ====
    param(
      'expect_reply',
      expected_io=expect.Reply('yes'),
      ios=lambda: AssertEquals(input(), 'yes'),
      error_message=None),

    param(
      'expect_reply_with_prompt',
      expected_io=(
        expect.InOrder(
          expect.Equals('Will it work? '),
          expect.Reply('yes'))),
      ios=lambda: AssertEquals(input('Will it work? '), 'yes'),
      error_message=None),

    # ==== Syntactic sugars ====
    param(
      'short_syntax_expect_in_order_equals',
      expected_io=['First expected output',
                   'Second expected output',
                   'Third expected output'],
      ios=lambda: (print('First expected output'),
                   print('Second expected output'),
                   print('Third expected output')),
      error_message=None),

    param(
      'short_syntax_expect_repeatedly_contains',
      expected_io=expect.Repeatedly('out'),
      ios=lambda: (print('Expected output'),
                   print('Expected output'),
                   print('Expected output')),
      error_message=None),

    param(
      'short_syntax_expect_repeatedly_contains_in_order',
      expected_io=expect.Repeatedly(['a', 'b']),
      ios=lambda: (print('a'),
                   print('b'),
                   print('a'),
                   print('b')),
      error_message=None),
  ])
  def test_expectation(self, test_name, expected_io, ios, error_message):
    self._io.set_expected_io(expected_io)
    ios()
    if error_message is None:
      self._io.assert_expectations_fulfilled()
    else:
      with self.assertRaises(AssertionError) as error:
        self._io.assert_expectations_fulfilled()
      if error_message:
        self.assertEqual(error_message, str(error.exception))

  def test_documentation_example(self):
    self._io.set_expected_io(
      expect.InOrder(
        expect.Contains('initialization'),
        expect.Anything().repeatedly(),
        expect.Equals('Proceed?'),
        expect.Reply('yes'),
        expect.Prefix('Success')))

    print('Program initialization...')
    print('Loading resources...')
    print('Initialization complete.')
    print('Proceed? ')
    if input() == 'yes':
      print('Success')
    else:
      print('Aborting')

    self._io.assert_expectations_fulfilled()

  def test_output_was(self):
    print('Some output')
    self._io.assert_output_was('Some output')
    print('Some more output')
    self._io.assert_output_was('Some more output')

  def test_set_expected_io_ignore_previous_outputs(self):
    print('Some ignored output')
    self._io.set_expected_io('Some expected output')
    print('Some expected output')
    self._io.assert_expectations_fulfilled()


if __name__ == '__main__':
  unittest.main()

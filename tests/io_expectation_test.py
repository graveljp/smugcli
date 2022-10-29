"""Test for io_expectation.py."""

import sys
import unittest

from parameterized import parameterized, param

import io_expectation as expect


def assert_equals(lhs, rhs):
  """Asserts that `lhs` equals `rhs`. Usable at the global scope."""
  if lhs != rhs:
    raise AssertionError(f'Strings are not equals: {lhs} != {rhs}')


class IoExpectationTest(unittest.TestCase):
  """Tests for the class `io_expectation.ExpectedInputOutput`."""

  def setUp(self):
    self._io = expect.ExpectedInputOutput()
    sys.stdin = self._io
    sys.stdout = self._io

  def tearDown(self):
    self._io.close()

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
          error_message=("Pending IO expectation never fulfilled:\n"
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
          error_message=(
              "No more output expected, but got: 'Unexpected output\n'")),

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
          error_message=("Pending IO expectation never fulfilled:\n"
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
          error_message=(
              "No more output expected, but got: 'Unexpected output\n'")),


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
          error_message=("Pending IO expectation never fulfilled:\n"
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
          error_message=(
              "No more output expected, but got: 'Unexpected output\n'")),

      # ==== expect.Regex ====
      param(
          'expect_regex',
          expected_io=expect.Regex('.*out.ut'),
          ios=lambda: print('Expected output'),
          error_message=None),

      param(
          'expect_regex_allows_partial_match',
          expected_io=expect.Regex('.*out.u'),
          ios=lambda: print('Expected output'),
          error_message=None),

      param(
          'expect_regex_can_require_full_match',
          expected_io=expect.Regex('.*out.u$'),
          ios=lambda: print('Expected output'),
          error_message=("Unexpected output:\n"
                         "- Regex('.*out.u$')\n"
                         "+ 'Expected output\\n'")),

      param(
          'expect_regex_no_output',
          expected_io=expect.Regex('.*out.ut'),
          ios=lambda: None,
          error_message=("Pending IO expectation never fulfilled:\n"
                         "Regex('.*out.ut')")),

      param(
          'expect_regex_mismatch',
          expected_io=expect.Regex('Expect.*put'),
          ios=lambda: print('Something else'),
          error_message=("Unexpected output:\n"
                         "- Regex('Expect.*put')\n"
                         "+ 'Something else\\n'")),

      param(
          'expect_regex_extra_output',
          expected_io=expect.Regex('Expect.*put'),
          ios=lambda: (print('Expected output'),
                       print('Unexpected output')),
          error_message=(
              "No more output expected, but got: 'Unexpected output\n'")),

      # ==== expect.Anything ====
      param(
          'expect_anything_success',
          expected_io=expect.Anything(),
          ios=lambda: print('Some output'),
          error_message=None),

      param(
          'expect_anything_no_output',
          expected_io=expect.Anything(),
          ios=lambda: None,
          error_message=("Pending IO expectation never fulfilled:\n"
                         "Anything()")),

      param(
          'expect_anything_extra_output',
          expected_io=expect.Anything(),
          ios=lambda: (print('Some output'),
                       print('Some more output')),
          error_message=(
              "No more output expected, but got: 'Some more output\n'")),

      # ==== expect.And ====
      param(
          'expect_and',
          expected_io=expect.And('Some', 'out'),
          ios=lambda: print('Some output'),
          error_message=None),

      param(
          'expect_and_no_output',
          expected_io=expect.And('Some', 'out'),
          ios=lambda: None,
          error_message=("Pending IO expectation never fulfilled:\n"
                         "Contains('Some') and Contains('out')")),

      param(
          'expect_and_lhs_fails',
          expected_io=expect.And('Some', 'out'),
          ios=lambda: print('Other output'),
          error_message=("Unexpected output:\n"
                         "- Contains('Some') and Contains('out')\n"
                         "+ 'Other output\\n'")),

      param(
          'expect_and_rhs_fails',
          expected_io=expect.And('Some', 'out'),
          ios=lambda: print('Some string'),
          error_message=("Unexpected output:\n"
                         "- Contains('out')\n"
                         "+ 'Some string\\n'")),

      param(
          'expect_and_both_fails',
          expected_io=expect.And('Some', 'out'),
          ios=lambda: print('Other string'),
          error_message=("Unexpected output:\n"
                         "- Contains('Some') and Contains('out')\n"
                         "+ 'Other string\\n'")),

      param(
          'expect_and_many_arguments',
          expected_io=expect.And('foo', 'bar', 'baz', 'buz'),
          ios=lambda: print('String: buz foo baz bar.'),
          error_message=None),

      param(
          'expect_and_many_arguments_error',
          expected_io=expect.And('foo', 'bar', 'baz', 'buz'),
          ios=lambda: print('String: buz foo bar.'),
          error_message=(
              "Unexpected output:\n"
              "- Contains('baz') and Contains('buz')\n"
              "+ 'String: buz foo bar.\\n'")),

      param(
          'expect_and_short_syntax',
          expected_io=expect.Contains('Some') & expect.Contains('out'),
          ios=lambda: print('Some output'),
          error_message=None),

      param(
          'expect_and_short_syntax_no_output',
          expected_io=expect.Contains('Some') & expect.Contains('out'),
          ios=lambda: None,
          error_message=("Pending IO expectation never fulfilled:\n"
                         "Contains('Some') and Contains('out')")),

      param(
          'expect_and_short_syntax_lhs_fails',
          expected_io=expect.Contains('Some') & expect.Contains('out'),
          ios=lambda: print('Other output'),
          error_message=("Unexpected output:\n"
                         "- Contains('Some') and Contains('out')\n"
                         "+ 'Other output\\n'")),

      param(
          'expect_and_short_syntax_rhs_fails',
          expected_io=expect.Contains('Some') & expect.Contains('out'),
          ios=lambda: print('Some string'),
          error_message=("Unexpected output:\n"
                         "- Contains('out')\n"
                         "+ 'Some string\\n'")),

      param(
          'expect_and_short_syntax_both_fails',
          expected_io=expect.Contains('Some') & expect.Contains('out'),
          ios=lambda: print('Other string'),
          error_message=("Unexpected output:\n"
                         "- Contains('Some') and Contains('out')\n"
                         "+ 'Other string\\n'")),

      # ==== expect.Or ====
      param(
          'expect_or',
          expected_io=expect.Or('Some', 'out'),
          ios=lambda: print('Some output'),
          error_message=None),

      param(
          'expect_or_no_output',
          expected_io=expect.Or('Some', 'out'),
          ios=lambda: None,
          error_message=("Pending IO expectation never fulfilled:\n"
                         "Contains('Some') or Contains('out')")),

      param(
          'expect_or_lhs_fails',
          expected_io=expect.Or('Some', 'out'),
          ios=lambda: print('Other output'),
          error_message=None),

      param(
          'expect_or_rhs_fails',
          expected_io=expect.Or('Some', 'out'),
          ios=lambda: print('Some string'),
          error_message=None),

      param(
          'expect_or_both_fails',
          expected_io=expect.Or('Some', 'out'),
          ios=lambda: print('Other string'),
          error_message=("Unexpected output:\n"
                         "- Contains('Some') or Contains('out')\n"
                         "+ 'Other string\\n'")),

      param(
          'expect_or_many_arguments',
          expected_io=expect.Or('foo', 'bar', 'baz', 'buz'),
          ios=lambda: print('String: buz.'),
          error_message=None),

      param(
          'expect_or_many_arguments_error',
          expected_io=expect.Or('foo', 'bar', 'baz', 'buz'),
          ios=lambda: print('Unexpected'),
          error_message=(
              "Unexpected output:\n"
              "- Contains('foo') or Contains('bar')"
              " or Contains('baz') or Contains('buz')\n"
              "+ 'Unexpected\\n'")),

      param(
          'expect_or_short_syntax',
          expected_io=expect.Contains('Some') | expect.Contains('out'),
          ios=lambda: print('Some output'),
          error_message=None),

      param(
          'expect_or_short_syntax_no_output',
          expected_io=expect.Contains('Some') | expect.Contains('out'),
          ios=lambda: None,
          error_message=("Pending IO expectation never fulfilled:\n"
                         "Contains('Some') or Contains('out')")),

      param(
          'expect_or_short_syntax_lhs_fails',
          expected_io=expect.Contains('Some') | expect.Contains('out'),
          ios=lambda: print('Other output'),
          error_message=None),

      param(
          'expect_or_short_syntax_rhs_fails',
          expected_io=expect.Contains('Some') | expect.Contains('out'),
          ios=lambda: print('Some string'),
          error_message=None),

      param(
          'expect_or_short_syntax_both_fails',
          expected_io=expect.Contains('Some') | expect.Contains('out'),
          ios=lambda: print('Other string'),
          error_message=("Unexpected output:\n"
                         "- Contains('Some') or Contains('out')\n"
                         "+ 'Other string\\n'")),

      # ==== expect.Not ====
      param(
          'expect_not_equals',
          expected_io=expect.Not(expect.Equals('Unexpected string')),
          ios=lambda: (print('Expected string')),
          error_message=None),

      param(
          'expect_not_equals_error',
          expected_io=expect.Not(expect.Equals('Unexpected string')),
          ios=lambda: (print('Unexpected string')),
          error_message=("Unexpected output:\n"
                         "- Not(Equals('Unexpected string'))\n"
                         "+ 'Unexpected string\\n'")),

      param(
          'expect_not_equals_or_equals',
          expected_io=expect.Not(expect.Equals('Unexpected 1') |
                                 expect.Equals('Unexpected 2')),
          ios=lambda: (print('Expected string')),
          error_message=None),

      param(
          'expect_not_equals_or_equals_error',
          expected_io=expect.Not(expect.Equals('Unexpected 1') |
                                 expect.Equals('Unexpected 2')),
          ios=lambda: (print('Unexpected 2')),
          error_message=("Unexpected output:\n"
                         "- Not(Equals('Unexpected 2'))\n"
                         "+ 'Unexpected 2\\n'")),

      param(
          'expect_not_equals_repeatedly',
          expected_io=expect.Not(expect.Equals('Unexpected')).repeatedly(),
          ios=lambda: (print('Expected 1'),
                       print('Expected 2')),
          error_message=None),

      param(
          'expect_not_equals_repeatedly_error',
          expected_io=expect.Not(expect.Equals('Unexpected')).repeatedly(),
          ios=lambda: (print('Expected 1'),
                       print('Unexpected')),
          error_message=("Unexpected output:\n"
                         "- Repeatedly(Not(Equals('Unexpected')))\n"
                         "+ 'Unexpected\\n'")),

      param(
          'expect_not_equals_and_not_equals_repeatedly',
          expected_io=(expect.Not(expect.Equals('Unexpected 1')) &
                       expect.Not(expect.Equals('Unexpected 2'))).repeatedly(),
          ios=lambda: (print('Expected 1'),
                       print('Expected 2'),
                       print('Expected 3')),
          error_message=None),

      param(
          'expect_not_equals_and_not_equals_repeatedly_error',
          expected_io=(expect.Not(expect.Equals('Unexpected 1')) &
                       expect.Not(expect.Equals('Unexpected 2'))).repeatedly(),
          ios=lambda: (print('Expected 1'),
                       print('Expected 2'),
                       print('Unexpected 1')),
          error_message=(
              "Unexpected output:\n"
              "- Repeatedly(Not(Equals('Unexpected 1')) and "
              "Not(Equals('Unexpected 2')))\n"
              "+ 'Unexpected 1\\n'")),

      param(
          'expect_not_equals_or_equals_repeatedly',
          expected_io=expect.Not(expect.Equals('Unexpected 1') |
                                 expect.Equals('Unexpected 2')).repeatedly(),
          ios=lambda: (print('Expected 1'),
                       print('Expected 2'),
                       print('Expected 3')),
          error_message=None),

      param(
          'expect_not_equals_or_equals_repeatedly_error_1',
          expected_io=expect.Not(expect.Equals('Unexpected 1') |
                                 expect.Equals('Unexpected 2')).repeatedly(),
          ios=lambda: (print('Expected 1'),
                       print('Expected 2'),
                       print('Unexpected 2')),
          error_message=("Unexpected output:\n"
                         "- Repeatedly(Not(Equals('Unexpected 2')))\n"
                         "+ 'Unexpected 2\\n'")),

      param(
          'expect_not_equals_or_equals_repeatedly_error_2',
          expected_io=expect.Not(expect.Equals('Other 1') |
                                 expect.Equals('Other 2')).repeatedly(),
          ios=lambda: (print('Expected 1'),
                       print('Other 1'),
                       print('Expected 2'),
                       print('Other 2')),
          error_message=(
              "Unexpected output:\n"
              "- Repeatedly(Not(Equals('Other 1') or Equals('Other 2')))\n"
              "+ 'Other 1\\n'")),

      param(
          'expect_in_order_not',
          expected_io=expect.InOrder(
              expect.Equals('Expected 1'),
              expect.Not(expect.Equals('Unexpected 1')),
              expect.Equals('Expected 2'),
              expect.Not(expect.Equals('Unexpected 2'))),
          ios=lambda: (print('Expected 1'),
                       print('Something else 1'),
                       print('Expected 2'),
                       print('Something else 2')),
          error_message=None),

      param(
          'expect_in_order_not_error',
          expected_io=expect.InOrder(
              expect.Equals('Expected 1'),
              expect.Not(expect.Equals('Unexpected')),
              expect.Equals('Expected 2')),
          ios=lambda: (print('Expected 1'),
                       print('Unexpected'),
                       print('Expected 2')),
          error_message=(
              "Unexpected output:\n"
              "- InOrder(Not(Equals('Unexpected')), Equals('Expected 2'))\n"
              "+ 'Unexpected\\n'")),

      param(
          'expect_any_order_not',
          expected_io=expect.AnyOrder(
              expect.Equals('Expected 1'),
              expect.Not(expect.Equals('Unexpected 1')),
              expect.Equals('Expected 2'),
              expect.Not(expect.Equals('Unexpected 2')),
              expect.Equals('Expected 3')),
          ios=lambda: (print('Expected 3'),
                       print('Something else 2'),
                       print('Expected 2'),
                       print('Something else 1'),
                       print('Expected 1')),
          error_message=None),

      param(
          'expect_any_order_not_error',
          expected_io=expect.AnyOrder(
              expect.Equals('Expected 1'),
              expect.Not(expect.Equals('Unexpected')),
              expect.Equals('Expected 2')),
          ios=lambda: (print('Expected 2'),
                       print('Unexpected'),
                       print('Expected 1')),
          error_message=(
              "Unexpected output:\n"
              "- AnyOrder(Equals('Expected 1'), Not(Equals('Unexpected')))\n"
              "+ 'Unexpected\\n'")),

      param(
          'expect_any_order_anything_but',
          expected_io=expect.AnyOrder(
              expect.Not(expect.Equals('Unexpected 1') |
                         expect.Equals('Unexpected 2')).repeatedly(),
              expect.Equals('Expected 1'),
              expect.Equals('Expected 2')),
          ios=lambda: (print('Expected 2'),
                       print('Something else 1'),
                       print('Something else 2'),
                       print('Expected 1')),
          error_message=None),

      param(
          'expect_any_order_anything_but_error',
          expected_io=expect.AnyOrder(
              expect.Not(expect.Equals('Other 1') |
                         expect.Equals('Other 2')).repeatedly(),
              expect.Equals('Expected')),
          ios=lambda: (print('Expected'),
                       print('Other 2')),
          error_message=(
              "Unexpected output:\n"
              "- Repeatedly(Not(Equals('Other 1') or Equals('Other 2')))\n"
              "+ 'Other 2\\n'")),

      # ==== Repeatedly ====
      param(
          'expect_repeatedly',
          expected_io=expect.Repeatedly(expect.Equals('Expected output')),
          ios=lambda: (print('Expected output'),
                       print('Expected output'),
                       print('Expected output')),
          error_message=None),

      param(
          'expect_repeatedly_error',
          expected_io=expect.Repeatedly(expect.Equals('Expected output')),
          ios=lambda: (print('Expected output'),
                       print('Expected output'),
                       print('Unexpected output')),
          error_message=("Unexpected output:\n"
                         "- Repeatedly(Equals('Expected output'))\n"
                         "+ 'Unexpected output\\n'")),

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
          error_message=("Pending IO expectation never fulfilled:\n"
                         "Repeatedly(Equals('Expected output'), 2, 4)")),

      param(
          'expect_repeatedly_equals_below_min',
          expected_io=expect.Repeatedly(expect.Equals('Expected output'), 2, 4),
          ios=lambda: print('Expected output'),
          error_message=("Pending IO expectation never fulfilled:\n"
                         "Repeatedly(Equals('Expected output'), 1, 3)")),

      param(
          'expect_repeatedly_equals_above_max',
          expected_io=expect.Repeatedly(expect.Equals('Expected'), 2, 4),
          ios=lambda: (print('Expected'),
                       print('Expected'),
                       print('Expected'),
                       print('Expected'),
                       print('Expected')),
          error_message="No more output expected, but got: 'Expected\n'"),

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
          'expect_indefinitely_repeating_short_syntax_1',
          expected_io=expect.Repeatedly(['a', 'b']),
          ios=lambda: (print('a'),
                       print('b'),
                       print('a'),
                       print('b')),
          error_message=None),

      param(
          'expect_indefinitely_repeating_short_syntax_1_error',
          expected_io=expect.Repeatedly(['a', 'b']),
          ios=lambda: (print('a'),
                       print('b'),
                       print('b'),
                       print('a')),
          error_message=("Unexpected output:\n"
                         "- Repeatedly(InOrder(Contains('a'), Contains('b')))\n"
                         "+ 'b\\n'")),

      param(
          'expect_indefinitely_repeating_short_syntax_2',
          expected_io=expect.InOrder('a', 'b').repeatedly(),
          ios=lambda: (print('a'),
                       print('b'),
                       print('a'),
                       print('b')),
          error_message=None),

      param(
          'expect_indefinitely_repeating_short_syntax_2_error',
          expected_io=expect.InOrder('a', 'b').repeatedly(),
          ios=lambda: (print('a'),
                       print('b'),
                       print('b'),
                       print('a')),
          error_message=("Unexpected output:\n"
                         "- Repeatedly(InOrder(Contains('a'), Contains('b')))\n"
                         "+ 'b\\n'")),

      param(
          'expect_repeatedly_equals_short_syntax_below_min',
          expected_io=expect.Equals('Expected output').repeatedly(2, 4),
          ios=lambda: print('Expected output'),
          error_message=("Pending IO expectation never fulfilled:\n"
                         "Repeatedly(Equals('Expected output'), 1, 3)")),

      param(
          'expect_repeatedly_equals_short_syntax_above_max',
          expected_io=expect.Equals('Expected output').repeatedly(2, 4),
          ios=lambda: (print('Expected output'),
                       print('Expected output'),
                       print('Expected output'),
                       print('Expected output'),
                       print('Expected output')),
          error_message=(
              "No more output expected, but got: 'Expected output\n'")),


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
          error_message=(
              "No more output expected, but got: 'Unexpected output\n'")),

      param(
          'expect_in_order_repeatedly',
          expected_io=expect.InOrder(
              expect.Equals('Repeated output').times(2, 4),
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
                      expect.Equals('Repeated output').times(2, 4),
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

      # ==== Url ====
      param(
          'expect_url_equals',
          expected_io=expect.Url(expect.Equals('http://foo.com/bar')),
          ios=lambda: print('http://foo.com/bar'),
          error_message=None),

      param(
          'expect_url_equals_error',
          expected_io=expect.Url(expect.Equals('http://foo.com/bar')),
          ios=lambda: print('http://bar.com/bar'),
          error_message=("Unexpected output:\n"
                         "- Url(Equals('http://foo.com/bar'))\n"
                         "+ 'http://bar.com/bar\\n'")),

      param(
          'expect_url_default_sub_expectation',
          expected_io=expect.Url('foo.com'),
          ios=lambda: print('http://foo.com/bar'),
          error_message=None),

      param(
          'expect_url_in_order',
          expected_io=expect.Url(['http://foo.com/for',
                                  'http://bar.com/bar']),
          ios=lambda: (print('http://foo.com/for'),
                       print('http://bar.com/bar')),
          error_message=None),

      # ==== Reply ====
      param(
          'expect_reply',
          expected_io=expect.Reply('yes'),
          ios=lambda: assert_equals(input(), 'yes'),
          error_message=None),

      param(
          'expect_reply_with_prompt',
          expected_io=(
              expect.InOrder(
                  expect.Equals('Will it work? '),
                  expect.Reply('yes'))),
          ios=lambda: assert_equals(input('Will it work? '), 'yes'),
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
    """Parameterized test validating io expectations."""
    del test_name  # Unused.
    self._io.set_expected_io(expected_io)
    ios()
    if error_message is None:
      self._io.assert_expectations_fulfilled()
    else:
      with self.assertRaises(AssertionError) as error:
        self._io.assert_expectations_fulfilled()
      if error_message is not None:
        self.assertEqual(error_message, str(error.exception))

  def test_documentation_example(self):
    """Test the example provided in the documentation."""
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
    """Tests the `assert_output_was` method."""
    print('Some output')
    self._io.assert_output_was('Some output')
    print('Some more output')
    self._io.assert_output_was('Some more output')

  def test_set_expected_io_ignore_previous_outputs(self):
    """Only IOs happening after setting expectations are considered."""
    print('Some ignored output')
    self._io.set_expected_io('Some expected output')
    print('Some expected output')
    self._io.assert_expectations_fulfilled()


if __name__ == '__main__':
  unittest.main()

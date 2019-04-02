#!/usr/bin/python

import argparse
import os
import sys
import unittest

def main():
  parser = argparse.ArgumentParser(
    description='Run (all) unit tests.')

  parser.add_argument('--reset_cache',
                      action='store_true',
                      help=('If True, remove cached HTTP request responses and '
                            'run the tests againsts the real SmugMug backend. '
                            'If False, HTTP request responses will be replayed '
                            'from the last test run.'))
  parser.add_argument('tests',
                      nargs='*',
                      default=['discover', '-p', '*_test.py'],
                      help='Unit tests to run. Run all tests if not specified.')

  parsed = parser.parse_args()

  if parsed.reset_cache:
    os.environ['RESET_CACHE'] = 'True'

  unittest.main(module=None, argv=['run_tests.py'] + parsed.tests)

if __name__ == '__main__':
  main()

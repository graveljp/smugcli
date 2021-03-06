import setuptools
import sys

install_requires = [
  # For authentification and communication with SmugMug.
  'bottle>=0.12.13',
  'rauth>=0.7.3',
  'requests>=2.13.0',
  'requests-oauthlib>=0.7.0',

  # To make ANSI escape character sequences work on Windows.
  'colorama>=0.3.9; platform_system=="Windows"',

  # For parsing metadata from local files:
  'hachoir>=3.0',
  'six>=1.15.0'
]

with open('README.md', 'r') as fh:
  long_description = fh.read()

with open('smugcli/version.py') as fh:
  exec(fh.read())

setuptools.setup(
  name='smugcli',
  version=__version__,
  author='Jean-Philippe Gravel',
  author_email='jpgravel@gmail.com',
  description='Command line tool for SmugMug',
  long_description=long_description,
  long_description_content_type='text/markdown',
  url='https://github.com/graveljp/smugcli',
  packages=setuptools.find_packages(),
  classifiers=[
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
  ],
  install_requires=install_requires,
  entry_points={
    'console_scripts': [
      'smugcli=smugcli.smugcli:main',
    ],
  },
)

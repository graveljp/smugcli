import setuptools
import sys

with open('requirements.txt') as fh:
  install_requires = [l for l in fh.read().splitlines()
                      if l.strip() and not l.strip().startswith('#')]

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
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
  ],
  install_requires=install_requires,
  entry_points={
    'console_scripts': [
      'smugcli=smugcli.smugcli:main',
    ],
  },
)

"""Setup script for building SmugCLI."""

import locale
import setuptools
from smugcli import version

with open('requirements.txt', encoding=locale.getpreferredencoding()) as file:
  install_requires = [line for line in file.read().splitlines()
                      if line.strip() and not line.strip().startswith('#')]

with open('README.md', 'r', encoding=locale.getpreferredencoding()) as file:
  long_description = file.read()

setuptools.setup(
    name='smugcli',
    version=version.__version__,
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

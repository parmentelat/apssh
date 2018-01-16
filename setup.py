#!/usr/bin/env python3

import sys
import setuptools

# don't try to import the apssh package at this early point
# as this would require asyncssh which might not be installed yet
from apssh.version import version as __version__

# check python version
from sys import version_info
major, minor= version_info[0:2]
if not (major == 3 and minor >= 5):
    print("python 3.5 or higher is required")
    exit(1)

long_description = "See README at https://github.com/parmentelat/apssh/blob/master/README.md"

### requirements - used by pip install
# *NOTE* for ubuntu, to install asyncssh, also run this beforehand
# apt-get -y install libffi-dev libssl-dev
# which is required before pip can install asyncssh
required_modules = [
    'asyncssh',
    'asynciojobs', 
]

setuptools.setup(
    name             = "apssh",
    version          = __version__,
    author           = "Thierry Parmentelat",
    author_email     = "thierry.parmentelat@inria.fr",
    description      = "Asynchroneous Parallel ssh",
    long_description = long_description,
    license          = "CC BY-SA 4.0",
    download_url     = "http://github/build.onelab.eu/apssh/apssh-{v}.tar.gz".format(v=__version__),
    url              = "http://nepi-ng.inria.fr/apssh",
    packages         = [ 'apssh' ],
    install_requires = required_modules,
    classifiers = [
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Information Technology",
        "Programming Language :: Python :: 3.5",
        ],
    entry_points = {
        'console_scripts' : [
            'apssh = apssh.__main__:main'
        ]
    }
)


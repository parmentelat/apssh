#!/usr/bin/env python3

from __future__ import print_function

import sys
import os
import os.path
from distutils.core import setup
from apssh.version import version as apssh_version

# check python version
from sys import version_info
major, minor= version_info[0:2]
if not (major == 3 and minor >= 5):
    print("python 3.5 or higher is required")
    exit(1)

# read licence info
with open("COPYING") as f:
    license = f.read()
with open("README.md") as f:
    long_description = f.read()

### requirements - used by pip install
# *NOTE* for ubuntu: also run this beforehand
# apt-get -y install libffi-dev
# which is required before pip can install asyncssh
required_modules = [
    'asyncssh',
    'asynciojobs', 
]

setup(
    name             = "apssh",
    version          = apssh_version,
    description      = "Asynchroneous Parallel ssh",
    long_description = long_description,
    license          = license,
    author           = "Thierry Parmentelat",
    author_email     = "thierry.parmentelat@inria.fr",
    download_url     = "http://github/build.onelab.eu/apssh/apssh-{v}.tar.gz".format(v=apssh_version),
    url              = "https://github.com/parmentelat/fitsophia/tree/master/apssh",
    platforms        = "Linux",
    packages         = [ 'apssh', 'apssh.jobs' ],
    scripts          = [ 'bin/apssh'],
    install_requires = required_modules,
)


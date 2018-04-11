#!/usr/bin/env python3

"""
Packaging and installation for the apssh package
"""

from sys import version_info

import setuptools

# don't try to import the apssh package at this early point
# as this would require asyncssh which might not be installed yet
from apssh.version import __version__

# check python version
MAJOR, MINOR = version_info[0:2]
if not (MAJOR == 3 and MINOR >= 5):
    print("python 3.5 or higher is required")
    exit(1)


LONG_DESCRIPTION = \
    "See README at https://github.com/parmentelat/apssh/blob/master/README.md"

# requirements - used by pip install
# *NOTE* for ubuntu, to install asyncssh, at some point in time_ok
# there has been a need to also run this beforehand:
# apt-get -y install libffi-dev libssl-dev
# which is required before pip can install asyncssh
REQUIRED_MODULES = [
    'asyncssh',
    'asynciojobs',
]

# pylint: disable=c0326
setuptools.setup(
    name="apssh",
    version=__version__,
    author="Thierry Parmentelat",
    author_email="thierry.parmentelat@inria.fr",
    description="Asynchroneous Parallel ssh",
    long_description=LONG_DESCRIPTION,
    license="CC BY-SA 4.0",
    url="http://apssh.readthedocs.io/",
    packages=['apssh'],
    install_requires=REQUIRED_MODULES,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Information Technology",
        "Programming Language :: Python :: 3.5",
    ],
    entry_points={
        'console_scripts': [
            'apssh = apssh.__main__:main'
        ]
    }
)

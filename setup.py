#!/usr/bin/env python3

"""
Packaging and installation for the apssh package
"""

from pathlib import Path

import setuptools

# https://packaging.python.org/guides/single-sourcing-package-version/
# set __version__ by read & exec of the python code
# this is better than an import that would otherwise try to
# import the whole package, and fail if a required module is not yet there
VERSION_FILE = Path(__file__).parent / "apssh" / "version.py"
ENV = {}
with VERSION_FILE.open() as f:
    exec(f.read(), ENV)                                 # pylint: disable=w0122
__version__ = ENV['__version__']

with open("README.md") as feed:
    LONG_DESCRIPTION = feed.read()

# requirements - used by pip install
# *NOTE* for ubuntu, to install asyncssh, at some point in time_ok
# there has been a need to also run this beforehand:
# apt-get -y install libffi-dev libssl-dev
# which is required before pip can install asyncssh
REQUIRED_MODULES = [
    'asyncssh',
    'asynciojobs',
    'jinja2',
]
TESTS_REQUIRE = [
    'nose',
    'psutil',
]

setuptools.setup(
    name="apssh",
    author="Thierry Parmentelat",
    author_email="thierry.parmentelat@inria.fr",
    description="Asynchroneous Parallel ssh",
    long_description=LONG_DESCRIPTION,
    long_description_content_type = "text/markdown",
    license="CC BY-SA 4.0",
    keywords=['asyncio', 'remote shell', 'parallel ssh'],

    packages=['apssh'],
    version=__version__,
    python_requires=">=3.5",

    entry_points={
        'console_scripts': [
            'apssh = apssh.__main__:main',
        ]
    },

    install_requires=REQUIRED_MODULES,
    tests_require=TESTS_REQUIRE,
    project_urls={
        'source': 'http://github.com/parmentelat/apssh',
        'documentation': 'http://apssh.readthedocs.io/',
    },

    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Information Technology",
        "Programming Language :: Python :: 3.5",
    ],
)

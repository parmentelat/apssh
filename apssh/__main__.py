#!/usr/bin/env python3

"""
The entry point for the apssh command
"""

# pylint: disable=missing-function-docstring

import sys

from apssh.cli import Apssh


def apssh():
    sys.exit(Apssh().main())

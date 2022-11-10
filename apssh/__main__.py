#!/usr/bin/env python3

"""
The entry point for the apssh command
"""

# pylint: disable=missing-function-docstring

import sys

from apssh.cli import Apssh, Appush


def apssh():
    sys.exit(Apssh().main())

def appush():
    sys.exit(Appush().main())

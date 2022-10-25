#!/usr/bin/env python3

"""
The entry point for the apssh command
"""

import sys

from apssh.apssh import Apssh


def main():                                             # pylint: disable=C0111
    sys.exit(Apssh().main())

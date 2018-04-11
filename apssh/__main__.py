#!/usr/bin/env python3

"""
The entry point for the apssh command
"""

from apssh.apssh import Apssh


def main():                                             # pylint: disable=C0111
    exit(Apssh().main())

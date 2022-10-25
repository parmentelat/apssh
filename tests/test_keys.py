#!/usr/bin/env python3

"""
Testing the keys loading features in apssh
"""

import unittest
from pathlib import Path

from apssh.keys import import_private_key, load_private_keys


class Tests(unittest.TestCase):

    def test_import(self):

        test_names = ['id_rsa', 'id-pass']

        for test_name in test_names:
            path = Path.home() / ".ssh" / test_name
            print(f"========== importing key from {path}")
            sshkey = import_private_key(path)
            print(f"-> got {sshkey}")

    def test_agent(self):
        for key in load_private_keys():
            print(f"Found in agent: {key}")

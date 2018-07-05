#!/usr/bin/env python3

"""
Testing the keys loading features in apssh
"""

# pylint: disable=c0111,r0201

import unittest
from pathlib import Path

from apssh.keys import import_private_key, load_private_keys


class Tests(unittest.TestCase):

    def test_import(self):

        test_names = ['id_rsa', 'id-pass']

        for test_name in test_names:
            path = Path.home() / ".ssh" / test_name
            print("========== importing key from {}".format(path))
            sshkey = import_private_key(path)
            print("-> got {}".format(sshkey))

    def test_agent(self):
        for key in load_private_keys():
            print("Found in agent: {}".format(key))


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3

import unittest

from apssh.keys import *


class Tests(unittest.TestCase):

    def test_import(self):

        test_names = ['id_rsa', 'id-pass']

        for test_name in test_names:
            path = Path("~/.ssh/{}".format(test_name)).expanduser()
            print("========== importing key from {}".format(path))
            sshkey = import_private_key(path)
            print("-> got {}".format(sshkey))

    def test_agent(self):
        for key in load_private_keys():
            print("Found in agent: {}".format(key))


if __name__ == '__main__':
    unittest.main()

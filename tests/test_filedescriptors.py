import unittest

import apssh
from . import util

class Tests(unittest.TestCase):

    def test_file_descriptor(self):
        fd_init = util.count_file_descriptors()
        for _ in range(100):
            apssh.SshNode('127.0.0.1')
        fd_end = util.count_file_descriptors()
        # 3 file desciptor open by unitttest ?
        self.assertLess(fd_end, fd_init+10)

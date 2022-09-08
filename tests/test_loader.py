# pylint: disable=c0111

import unittest
from pathlib import Path

from asynciojobs import Scheduler
from apssh import YamlLoader

from . import util

class Tests(unittest.TestCase):

    def test_loader_1(self):

        f = "tests/loader1.yaml"
        s1 = YamlLoader(f).load()

        p = Path("tests/loader1.yaml")
        s2 = YamlLoader(p).load()

        # there's not such operation as s1 == s2
        self.assertTrue( len(s1) == len(s2) == 8)
        util.produce_png(s1, "graphic-loader1-file")
        util.produce_png(s1, "graphic-loader1-path")

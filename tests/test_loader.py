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

    def test_loader_2(self):

        p = Path("tests/loader2.yaml.j2")
        jinja_variables = {
            'gateway': 'faraday.inria.fr',
            'leader': 'sopnode-l1.inria.fr',
            'verbose': True,
            'namespace': 'oai5g',
            'nodes': {
                'amf': 'fit01',
                'gnb': 'fit02',
            },
        }

        nodes_map, jobs_map, s = YamlLoader(p).load_with_maps(jinja_variables)

        self.assertTrue( len(s) == 8)
        init_demo = jobs_map['init_demo']
        self.assertIn('fit01', init_demo.label)

        util.produce_png(s, "graphic-loader2")

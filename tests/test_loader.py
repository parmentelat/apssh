# pylint: disable=c0111

from cmath import exp
import unittest
from pathlib import Path

from asynciojobs import Scheduler
from apssh import YamlLoader

from . import util


class Tests(unittest.TestCase):

    def test_loader_1(self):
        """
        load plain yaml - no jinja - from str or Path
        """

        f = "tests/loader1.yaml"
        s1 = YamlLoader(f).load()

        p = Path("tests/loader1.yaml")
        s2 = YamlLoader(p).load()

        # there's not such operation as s1 == s2
        self.assertTrue( len(s1) == len(s2) == 8)
        util.produce_svg(s1, "graphic-loader1-file")
        util.produce_svg(s2, "graphic-loader1-path")

    def test_loader_2_1(self):
        """
        load a yaml + jinja2
        """

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

        nodes_map, jobs_map, s = (            # pylint: disable=unused-variable
            YamlLoader(p).load_with_maps(jinja_variables))

        self.assertTrue( len(s) == 8)
        init_demo = jobs_map['init_demo']
        self.assertIn('fit01', init_demo.label)

        util.produce_svg(s, "graphic-loader2")

    def test_loader_2_2(self):
        """
        check save_intermediate with True or a str
        """
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

        def expected():
            return (
                Path("tests/loader2.yaml"),
                Path("tests/loader2-explicit.yaml"),
            )
        for e in expected():
            if e.exists():
                print(f"removing {e}")
                e.unlink()

        nodes_map, jobs_map, s = (            # pylint: disable=unused-variable
            YamlLoader(p).load_with_maps(
                jinja_variables, save_intermediate=True))
        e1, e2 = expected()
        self.assertTrue(e1.exists())

        explicit = str(e2)
        nodes_map, jobs_map, s = YamlLoader(p).load_with_maps(
            jinja_variables, save_intermediate=explicit)
        e1, e2 = expected()
        self.assertTrue(e2.exists())

        with e1.open() as f1, e2.open() as f2:
            self.assertEqual(f1.read(), f2.read())

    def test_loader_3(self):
        """
        localnode in yaml
        """
        f = "tests/loader3.yaml"
        s = YamlLoader(f).load()

        self.assertEqual(len(s), 4)
        util.produce_svg(s, "graphic-loader3")

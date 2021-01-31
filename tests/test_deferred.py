import unittest

from asynciojobs import Scheduler

from apssh import (
    SshNode, SshJob, Run, Deferred, Variables,
    CaptureFormatter, TerminalFormatter,
)

from .util import localuser, localhostname

class Tests(unittest.TestCase):

    def test_variables(self):
        """
        just test the ability of using variables
        """

        s = Scheduler()
        f = CaptureFormatter()
        vars = Variables()
        vars.fetched = 'a simple variable'
        n = SshNode(localhostname(), username=localuser(), formatter=f)
        s.add(
            SshJob(
                node=n,
                commands=[
                    # Waring this is NOT an f-string
                    Run(Deferred("echo {fetched}", vars)),
                    ])
        )
        f.start_capture()
        s.run()
        captured = f.get_capture()

        expected = "a simple variable\n"
        self.assertEqual(captured, expected)

    # for visual test for now
    def testhide_format(self):
        s = Scheduler()
        f = TerminalFormatter("%Y:%H:%S - @host@:@line@",
                              verbose=True)
        n = SshNode(localhostname(), username=localuser(), formatter=f)
        s.add(SshJob(node=n, commands=[ Run("echo LINE1"), Run("echo LINE2")]))
        s.run()

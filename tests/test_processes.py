# pylint: disable=c0111

import unittest

from asynciojobs import Scheduler

from apssh import SshJob, LocalNode, Run, RunScript, RunString, SshNode
from apssh import HostFormatter, load_private_keys, CommandFailedError

#from apssh.util import co_close_ssh_from_sched

from . import util
#from . import utilps

class Tests(unittest.TestCase):

    def _allowed_signal(self, allowed_exits,
                       host="localhost", username=None):

        print(f"Testing allowed signal allowed_exits={allowed_exits}")

        # global timeout
        total = 4
        # scheduled duration
        long = 2
        # send signal after that amount
        short = 1
        # we always kill with TERM
        signal = "TERM"

        if username is None:
            username = util.localuser()
        node = SshNode(host, username=username)

        scheduler = Scheduler(timeout = total, critical=False)
        SshJob(node=node, scheduler=scheduler,
               command=Run(f"sleep {long}",
                           allowed_exits=allowed_exits))
        SshJob(node=node, scheduler=scheduler,
               command=f"sleep {short}; pkill -{signal} sleep")

        expected = signal in allowed_exits

        run = scheduler.run()
        scheduler.list()
        self.assertEqual(run, expected)

    def test_allowed_signal_regular(self):
        self._allowed_signal(allowed_exits=[])
    def test_allowed_signal_term(self):
        self._allowed_signal(allowed_exits=['TERM'])
    def test_allowed_signal_term_mix(self):
        self._allowed_signal(allowed_exits=['TERM', 100])
    def test_allowed_signal_term_foreign(self):
        self._allowed_signal(allowed_exits=[100])



    def _allowed_retcod(self, allowed_exits,
                       host="localhost", username=None):

        print(f"Testing allowed retcod allowed_exits={allowed_exits}")

        # global timeout
        total = 4
        # scheduled duration
        long = 1
        # we always exit code 100
        retcod = 1000

        if username is None:
            username = util.localuser()
        node = SshNode(host, username=username)

        scheduler = Scheduler(timeout = total, critical=False)
        SshJob(node=node, scheduler=scheduler,
               command=Run(f"sleep {long}; exit {retcod}",
                           allowed_exits=allowed_exits))

        expected = retcod in allowed_exits

        run = scheduler.run()
        scheduler.list()
        self.assertEqual(run, expected)

    def test_allowed_retcod_regular(self):
        self._allowed_retcod(allowed_exits=[])
    def test_allowed_retcod_term(self):
        self._allowed_retcod(allowed_exits=[100])
    def test_allowed_retcod_term_mix(self):
        self._allowed_retcod(allowed_exits=['TERM', 100])
    def test_allowed_retcod_term_foreign(self):
        self._allowed_retcod(allowed_exits=[100])

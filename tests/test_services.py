# pylint: disable=c0111, unspecified-encoding

import time
import os
from pathlib import Path

from unittest import TestCase

from asynciojobs import Scheduler, Sequence

from apssh import SshNode, SshJob, Run, Service, Variables, Capture
from apssh import close_ssh_in_scheduler

from .util import produce_svg
from .utilps import ProcessMonitor

class Tests(TestCase):

    def _simple(self, forever):

        # initially this was using tcpdump
        # however it exhibits issued related to
        # the ownership of the capturefile
        # which are totally orthogonal to our objective
        # storage = f"/tmp/TCPDUMP-{forever}.pcap"
        # status = f"/tmp/TCPDUMP-{forever}.status"

        storage = f"/tmp/TICK-{forever}.out"
        status = f"/tmp/TICK-{forever}.status"

        tick = Service(f"""bash -c "while true; do date; sleep 0.2; done > {storage}" """,
                          service_id='tick',
                          verbose=True)
        monitor = ProcessMonitor()

        scheduler = Scheduler()
        node = SshNode("localhost")

        SshJob(node, scheduler=scheduler,
               command=tick.start_command(),
               forever=forever)

        Sequence(
            SshJob(node,
                   command="sleep 1"),
            SshJob(node,
                   command=tick.status_command(output=status)),
            SshJob(node,
                   command="sleep 1"),
            SshJob(node,
                   command=tick.stop_command()),
            # could use a pull to retrieve both files but that's not required
            # since we run on localhost, so keep tests simple
            scheduler=scheduler,
        )

        # cleanup before we run
        paths = (Path(x) for x in (storage, status))
        for path in paths:
            if path.exists():
                path.unlink()
            self.assertFalse(path.exists())
        produce_svg(scheduler, f"service-{forever}")

        self.assertTrue(scheduler.run())
        scheduler.list()
        for path in paths:
            self.assertTrue(path.exists())

        with Path(status).open() as feed:
            contents = feed.read()
            for needle in ('Loaded: loaded', 'Active: active'):
                self.assertTrue(contents.find(needle) >= 0)

        close_ssh_in_scheduler(scheduler)

        # let it settle for a short while, and check the process space
        time.sleep(0.5)
        monitor.difference()

        news = monitor.news
        if news:
            print(f"we have {len(news)} new processes, {news}")
            ps_command = "ps " + "".join(str(pid) for pid in news)
            os.system(ps_command)

        self.assertEqual(len(news), 0)

    def test_simple_regular(self):
        return self._simple(forever=False)
    def test_simple_forever(self):
        return self._simple(forever=True)

    def test_environment(self):

        needle_foo = 'xxx-foo-xxx'
        needle_bar = 'xxx-bar-xxx'

        scheduler = Scheduler()
        node = SshNode("localhost")

        env = Variables()
        service = Service("env",
                          service_id='echo-environ',
                          environ={'FOO': needle_foo,
                                   'BAR': needle_bar,
                                   })
        SshJob(
            scheduler=scheduler,
            node=node,
            commands=[
                Run(service.start_command()),
                Run(service.journal_command(since='5s ago'),
                    capture=Capture('journal', env))
            ]
        )

        self.assertEqual(scheduler.run(), True)
        self.assertTrue(f"FOO={needle_foo}" in env.journal)
        self.assertTrue(f"BAR={needle_bar}" in env.journal)

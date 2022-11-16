# pylint: disable=too-many-locals

import unittest

import time
import asyncio

from asynciojobs import Scheduler

from apssh import close_ssh_in_scheduler
from apssh import SshNode, SshJob, HostFormatter

from apssh import topology_as_pngfile

from .util import localuser, in_out_connections


VERBOSE = False
# VERBOSE = True

def verbose(*args, **kwds):
    if not VERBOSE:
        return
    print(*args, **kwds)


class Tests(unittest.TestCase):

    def populate_sched(self, scheduler, jobs, nested=0, pack_job=1):

        if nested != 0:
            for cpt_job, job in enumerate(jobs):
                if cpt_job % pack_job == 0:
                    core_sched = Scheduler()
                top_sched = core_sched
                current_sched = core_sched
                for _ in range(nested-1):
                    top_sched = Scheduler()
                    top_sched.add(current_sched)
                    current_sched = top_sched
                core_sched.add(job)
                if cpt_job % pack_job == 0:
                    scheduler.add(top_sched)

            #scheds = [Scheduler(job, scheduler=scheduler) for job in jobs]

        else:
            for job in jobs:
                scheduler.add(job)

        return scheduler

    def hop1(self, hostname='localhost', username=None,
             *, c1, commands, s_command='echo hop1-{}-{}',
             nested_sched=(0, 1)):
        """
        create
          * <c1> connections to one node 1 hop away
          * and on each <commands> commands

        check current number of connections
        """
        if username is None:
            username = localuser()

        verbose(f"creating {c1} hop1-connections - "
                f"{commands} commands per conn - "
                f" to {username}@{hostname}")
        scheduler = Scheduler()
        nodes = []
        jobs = []
        for n in range(c1):
            node1 = SshNode(hostname, username=username,
                            formatter=HostFormatter(verbose=False))
            nodes.append(node1)
            for c in range(commands):
                jobs.append(SshJob(node=node1,
                                   command=s_command.format(n, c),
                                   ))
        scheduler = self.populate_sched(scheduler, jobs,
                                        nested=nested_sched[0],
                                        pack_job=nested_sched[1])
        expected = c1
        # record base status
        in0, out0 = in_out_connections()
        verbose(f"INITIAL count in={in0} out={out0}")
        scheduler.export_as_pngfile("debug")
        topology_as_pngfile(scheduler, "topology")
        scheduler.run()

        in1, out1 = in_out_connections()
        verbose(f"AFTER RUN in={in1} out={out1}")
        self.assertEqual(in1-in0, expected)
        self.assertEqual(out1-out0, expected)

        # cleanup
        close_ssh_in_scheduler(scheduler)

        in1, out1 = in_out_connections()
        verbose(f"AFTER CLEANUP in={in1} out={out1}")
        self.assertEqual(in1-in0, 0)
        self.assertEqual(out1-out0, 0)

    def hop2(self, hostname='localhost.localdomain', username=None,
             *, c1=1, c2=1, commands=1, s_command='echo hop2-{}-{}-{}',
             nested_sched=(0, 1)):
        """
        create
          * <c1> connections to one node 1 hop away
          * on each one, <c2> connections one hop behind
          * and on each <commands> commands

        check current number of connections
        """
        if username is None:
            username = localuser()

        verbose(f"creating {c1}x{c2} hop2-connections - "
                f"{commands} commands per conn "
                f" to {username}@{hostname}")
        scheduler = Scheduler(timeout=7)
        nodes = []
        #nodes2 = []
        jobs = []
        for n in range(c1):
            node1 = SshNode(hostname, username=username,
                            formatter=HostFormatter(verbose=False))
            nodes.append(node1)
            for m in range(c2):
                node2 = SshNode(hostname, username=username,
                                gateway=node1,
                                formatter=HostFormatter(verbose=False))
                nodes.append(node2)
                for c in range(commands):
                    jobs.append(SshJob(node=node2,
                                       command=s_command.format(n, m, c),
                                       ))

        scheduler = self.populate_sched(scheduler, jobs,
                                        nested=nested_sched[0],
                                        pack_job=nested_sched[1])
        # for each hop1 conn, there are 1 hop1 + c2 hop2 connections alive
        expected = c1 * (c2+1)
        scheduler.export_as_pngfile("debug")
        topology_as_pngfile(scheduler, "topology")

        # record base status
        in0, out0 = in_out_connections()

        verbose(f"INITIAL count in={in0} out={out0}")
    #    try:
        scheduler.run()
        #except Exception:
    #        pass
        in1, out1 = in_out_connections()
        verbose(f"AFTER RUN in={in1} out={out1}")
        self.assertEqual(in1-in0, expected)
        self.assertEqual(out1-out0, expected)

        # cleanup
        close_ssh_in_scheduler(scheduler)

        #Lets wait a little bit to count
        time.sleep(1)
        in1, out1 = in_out_connections()

        verbose(f"AFTER CLEANUP in={in1} out={out1}")
        self.assertEqual(in1-in0, 0)
        self.assertEqual(out1-out0, 0)

    def test_hop1_shared(self):
        self.hop1(c1=1, commands=4)

    def test_hop1_dup(self):
        self.hop1(c1=4, commands=1)

    def test_hop1_multi(self):
        self.hop1(c1=4, commands=4)


    def test_hop2_112(self):
        self.hop2(commands=2)

    def test_hop2_121(self):
        self.hop2(c2=2)

    def test_hop2_211(self):
        self.hop2(c1=2)

    def test_hop2_222(self):
        self.hop2(c1=2, c2=2, commands=2)

    def test_hop1_shared_sched(self):
        self.hop1(c1=1, commands=4)

    def test_hop1_shared_sched_nested11(self):
        self.hop1(c1=1, commands=4,
                  nested_sched=(1, 1))

    def test_hop1_shared_sched_nested21(self):
        self.hop1(c1=1, commands=4,
                  nested_sched=(2, 1))

    def test_hop1_shared_sched_nested12(self):
        self.hop1(c1=1, commands=4,
                  nested_sched=(1, 2))

    def test_hop1_shared_sched_nested22(self):
        self.hop1(c1=1, commands=4,
                  nested_sched=(2, 2))

    def test_hop1_dup_sched(self):
        self.hop1(c1=4, commands=1)

    def test_hop1_dup_sched_nested11(self):
        self.hop1(c1=4, commands=1,
                  nested_sched=(1, 1))

    def test_hop1_dup_sched_nested21(self):
        self.hop1(c1=4, commands=1,
                  nested_sched=(2, 1))

    def test_hop1_dup_sched_nested12(self):
        self.hop1(c1=4, commands=1,
                  nested_sched=(1, 2))

    def test_hop1_dup_sched_nested22(self):
        self.hop1(c1=4, commands=1,
                  nested_sched=(2, 2))

    def test_hop1_multi_sched(self):
        self.hop1(c1=4, commands=4)

    def test_hop1_multi_sched_nested11(self):
        self.hop1(c1=4, commands=4,
                  nested_sched=(1, 1))

    def test_hop1_multi_sched_nested21(self):
        self.hop1(c1=4, commands=4,
                  nested_sched=(2, 1))

    def test_hop1_multi_sched_nested12(self):
        self.hop1(c1=4, commands=4,
                nested_sched=(1, 2))

    def test_hop1_multi_sched_nested22(self):
        self.hop1(c1=4, commands=4,
                  nested_sched=(2, 2))

    def test_hop2_112_sched(self):
        self.hop2(commands=2)

    def test_hop2_112_sched_nested11(self):
        self.hop2(commands=2,
                  nested_sched=(1, 1))

    def test_hop2_112_sched_nested21(self):
        self.hop2(commands=2,
                  nested_sched=(2, 1))

    def test_hop2_112_sched_nested12(self):
        self.hop2(commands=2,
                  nested_sched=(1, 2))

    def test_hop2_112_sched_nested22(self):
        self.hop2(commands=2,
                  nested_sched=(2, 2))

    def test_hop2_121_sched(self):
        self.hop2(c2=2)

    def test_hop2_121_sched_nested11(self):
        self.hop2(c2=2,
                  nested_sched=(1, 1))

    def test_hop2_121_sched_nested21(self):
        self.hop2(c2=2,
                  nested_sched=(2, 1))

    def test_hop2_121_sched_nested12(self):
        self.hop2(c2=2,
                  nested_sched=(1, 2))

    def test_hop2_121_sched_nested22(self):
        self.hop2(c2=2,
                  nested_sched=(2, 2))

    def test_hop2_211_sched(self):
        self.hop2(c1=2)

    def test_hop2_211_sched_nested11(self):
        self.hop2(c1=2,
                  nested_sched=(1, 1))

    def test_hop2_211_sched_nested21(self):
        self.hop2(c1=2,
                  nested_sched=(2, 1))

    def test_hop2_211_sched_nested12(self):
        self.hop2(c1=2,
                  nested_sched=(1, 2))

    def test_hop2_211_sched_nested22(self):
        self.hop2(c1=2,
                  nested_sched=(2, 2))

    def test_hop2_222_sched(self):
        self.hop2(c1=2, c2=2, commands=2)

    def test_hop2_222_sched_nested11(self):
        self.hop2(c1=2, c2=2, commands=2,
                  nested_sched=(1, 1))

    def test_hop2_222_sched_nested21(self):
        self.hop2(c1=2, c2=2, commands=2,
                nested_sched=(2, 1))

    def test_hop2_222_sched_nested12(self):
        self.hop2(c1=2, c2=2, commands=2,
                  nested_sched=(1, 2))

    def test_hop2_222_sched_nested22(self):
        self.hop2(c1=2, c2=2, commands=2,
                  nested_sched=(2, 2))

    def test_hop_depth(self, hostname='localhost', username=None,
                       depth=4, commands=1):
        # Do not use the close_nodes manually on this test, it does keep the
        # Order of the declared nodes.

        if username is None:
            username = localuser()

        verbose(f"creating hop{depth}-connections - "
                f"{commands} commands per conn "
                f" to {username}@{hostname}")
        scheduler = Scheduler(timeout=7)
        nodes = []
        jobs = []
        gateway = None
        for n in range(depth):
            node = SshNode(hostname, gateway=gateway, username=username,
                           formatter=HostFormatter(verbose=False))
            nodes.append(node)
            gateway = node
            for c in range(commands):
                jobs.append(SshJob(node=node,
                                   command=f"echo hop{n}-{c}",
                                   scheduler=scheduler))

        expected = depth

        # record base status
        in0, out0 = in_out_connections()

        verbose(f"INITIAL count in={in0} out={out0}")
    #    try:
        scheduler.run()
        #except Exception:
    #        pass
        in1, out1 = in_out_connections()
        verbose(f"AFTER RUN in={in1} out={out1}")
        self.assertEqual(in1-in0, expected)
        self.assertEqual(out1-out0, expected)

        # cleanup
        close_ssh_in_scheduler(scheduler)

        #Lets wait a little bit to count
        time.sleep(1)
        in1, out1 = in_out_connections()

        verbose(f"AFTER CLEANUP in={in1} out={out1}")
        self.assertEqual(in1-in0, 0)
        self.assertEqual(out1-out0, 0)

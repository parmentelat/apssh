# pylint: disable=c0111

import unittest

import time
import asyncio

from asynciojobs import Scheduler

from apssh import util as uti
from apssh import SshNode, SshJob, ColonFormatter

from .util import localuser, in_out_connections


class Tests(unittest.TestCase):

    def close_sched(self, sched, dummy_bool=False):
        uti.close_ssh_from_sched(sched)
        #sched.close_connection()

    def close_nodes(self, nodes, gateway_first=True):
        if not gateway_first:
            nodes = nodes[::-1]
        try:
            gathered = asyncio.get_event_loop().run_until_complete(
                asyncio.gather(*(node.close() for node in nodes)))
        except ConnectionError:
            print("Received ConnectionError from close")

    def hop1(self, hostname='localhost', username=None,
             *, c1, commands, s_command='echo hop1-{}-{}',
             close_method=None):
        """
        create
          * <c1> connections to one node 1 hop away
          * and on each <commands> commands

        check current number of connections
        """
        if not close_method:
            close_method = self.close_nodes
        if username is None:
            username = localuser()

        print(f"creating {c1} hop1-connections - "
              f"{commands} commands per conn - "
              f" to {username}@{hostname}")
        scheduler = Scheduler()
        nodes = []
        jobs = []
        for n in range(c1):
            node1 = SshNode(hostname, username=username,
                            formatter=ColonFormatter(verbose=False))
            nodes.append(node1)
            for c in range(commands):
                jobs.append(SshJob(node=node1,
                                   command=s_command.format(n, c),
                                   scheduler=scheduler))

        expected = c1

        # record base status
        in0, out0 = in_out_connections()
        print(f"INITIAL count in={in0} out={out0}")

        scheduler.run()

        in1, out1 = in_out_connections()
        print(f"AFTER RUN in={in1} out={out1}")
        self.assertEqual(in1-in0, expected)
        self.assertEqual(out1-out0, expected)
        arg = nodes
        # cleanup
        if close_method != self.close_nodes:
            arg = scheduler
        close_method(arg)
        #self.close_nodes(nodes, gateway_first)
        in1, out1 = in_out_connections()
        print(f"AFTER CLEANUP in={in1} out={out1}")
        self.assertEqual(in1-in0, 0)
        self.assertEqual(out1-out0, 0)

    def hop2(self, hostname='localhost', username=None,
             *, c1=1, c2=1, commands=1, s_command='echo hop1-{}-{}-{}',
             close_method=None, gateway_first=True):
        """
        create
          * <c1> connections to one node 1 hop away
          * on each one, <c2> connections one hop behind
          * and on each <commands> commands

        check current number of connections
        """
        if not close_method:
            close_method = self.close_nodes
        if username is None:
            username = localuser()

        print(f"creating {c1}x{c2} hop2-connections - "
              f"{commands} commands per conn "
              f" to {username}@{hostname}")
        scheduler = Scheduler(timeout=7)
        nodes = []
        #nodes2 = []
        jobs = []
        for n in range(c1):
            node1 = SshNode(hostname, username=username,
                            formatter=ColonFormatter(verbose=False))
            nodes.append(node1)
            for m in range(c2):
                node2 = SshNode(hostname, username=username,
                                gateway=node1,
                                formatter=ColonFormatter(verbose=False))
                nodes.append(node2)
                for c in range(commands):
                    jobs.append(SshJob(node=node2,
                                       command=s_command.format(n, m, c),
                                       scheduler=scheduler))
        # for each hop1 conn, there are 1 hop1 + c2 hop2 connections alive
        expected = c1 * (c2+1)

        # record base status
        in0, out0 = in_out_connections()

        print(f"INITIAL count in={in0} out={out0}")
    #    try:
        scheduler.run()
        #except Exception:
    #        pass
        in1, out1 = in_out_connections()
        print(f"AFTER RUN in={in1} out={out1}")
        self.assertEqual(in1-in0, expected)
        self.assertEqual(out1-out0, expected)

        # cleanup
        # would be nice to find a way to check that the result
        # holds no matter in what order the cleanup is done
        arg = nodes
        # cleanup
        if close_method != self.close_nodes:
            arg = scheduler
        close_method(arg, gateway_first)
        #self.close_nodes(nodes, gateway_first)

        #Lets wait a little bit to count
        time.sleep(1)
        in1, out1 = in_out_connections()

        print(f"AFTER CLEANUP in={in1} out={out1}")
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
        self.hop1(c1=1, commands=4, close_method=self.close_sched)

    def test_hop1_dup_sched(self):
        self.hop1(c1=4, commands=1, close_method=self.close_sched)

    def test_hop1_multi_sched(self):
        self.hop1(c1=4, commands=4, close_method=self.close_sched)


    def test_hop2_112_sched(self):
        self.hop2(commands=2, close_method=self.close_sched)

    def test_hop2_121_sched(self):
        self.hop2(c2=2, close_method=self.close_sched)

    def test_hop2_211_sched(self):
        self.hop2(c1=2, close_method=self.close_sched)

    def test_hop2_222_sched(self):
        self.hop2(c1=2, c2=2, commands=2, close_method=self.close_sched)

    def test_hop_depth(self, hostname='localhost', username=None, depth=4,
                       commands=1, close_method=None, gateway_first=True):
        # Do not use the close_nodes manually on this test, it does keep the
        # Order of the declared nodes.

        if not close_method:
            close_method = self.close_sched
        if username is None:
            username = localuser()

        print(f"creating hop{depth}-connections - "
              f"{commands} commands per conn "
              f" to {username}@{hostname}")
        scheduler = Scheduler(timeout=7)
        nodes = []
        #nodes2 = []
        jobs = []
        gateway = None
        for n in range(depth):
            node = SshNode(hostname, gateway=gateway,username=username,
                           formatter=ColonFormatter(verbose=False))
            nodes.append(node)
            gateway = node
            print(id(node))
            for c in range(commands):
                jobs.append(SshJob(node=node,
                                   command=f"echo {n}-{c}",
                                   scheduler=scheduler))

        expected = depth

        # record base status
        in0, out0 = in_out_connections()

        print(f"INITIAL count in={in0} out={out0}")
    #    try:
        scheduler.run()
        #except Exception:
    #        pass
        in1, out1 = in_out_connections()
        print(f"AFTER RUN in={in1} out={out1}")
        self.assertEqual(in1-in0, expected)
        self.assertEqual(out1-out0, expected)

        # cleanup
        # would be nice to find a way to check that the result
        # holds no matter in what order the cleanup is done
        arg = nodes
        # cleanup
        if close_method != self.close_nodes:
            arg = scheduler
        close_method(arg, gateway_first)
        #self.close_nodes(nodes, gateway_first)

        #Lets wait a little bit to count
        time.sleep(1)
        in1, out1 = in_out_connections()

        print(f"AFTER CLEANUP in={in1} out={out1}")
        self.assertEqual(in1-in0, 0)
        self.assertEqual(out1-out0, 0)

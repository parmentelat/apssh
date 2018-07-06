# pylint: disable=c0111

import asyncio

from unittest import TestCase

from asynciojobs import Scheduler

from apssh import SshNode, SshJob, ColonFormatter

from .util import localuser, in_out_connections

class Tests(TestCase):

    def hop1(self, hostname='localhost', username=None,
             *, c1, commands):
        """
        create
          * <c1> connections to one node 1 hop away
          * and on each <commands> commands

        check current number of connections
        """
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
                                   command=f'echo hop1-{n}-{c}',
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

        # cleanup
        gathered = asyncio.get_event_loop().run_until_complete(
            asyncio.gather(*(node.close() for node in nodes)))
        in1, out1 = in_out_connections()
        print(f"AFTER CLEANUP in={in1} out={out1}")
        self.assertEqual(in1-in0, 0)
        self.assertEqual(out1-out0, 0)

    def hop2(self, hostname='localhost', username=None,
             *, c1=1, c2=1, commands=1):
        """
        create
          * <c1> connections to one node 1 hop away
          * on each one, <c2> connections one hop behind
          * and on each <commands> commands

        check current number of connections
        """
        if username is None:
            username = localuser()

        print(f"creating {c1}x{c2} hop2-connections - "
              f"{commands} commands per conn "
              f" to {username}@{hostname}")
        scheduler = Scheduler()
        nodes1 = []
        nodes2 = []
        jobs = []
        for n in range(c1):
            node1 = SshNode(hostname, username=username,
                            formatter=ColonFormatter(verbose=False))
            nodes1.append(node1)
            for m in range(c2):
                node2 = SshNode(hostname, username=username,
                                gateway=node1,
                                formatter=ColonFormatter(verbose=False))
                nodes2.append(node2)
                for c in range(commands):
                    jobs.append(SshJob(node=node2,
                                       command=f'echo hop1-{n}-{m}-{c}',
                                       scheduler=scheduler))

        # for each hop1 conn, there are 1 hop1 + c2 hop2 connections alive
        expected = c1 * (c2+1)

        # record base status
        in0, out0 = in_out_connections()
        print(f"INITIAL count in={in0} out={out0}")

        scheduler.run()

        in1, out1 = in_out_connections()
        print(f"AFTER RUN in={in1} out={out1}")
        self.assertEqual(in1-in0, expected)
        self.assertEqual(out1-out0, expected)

        # cleanup
        # would be nice to find a way to check that the result
        # holds no matter in what order the cleanup is done
        for nodeset in nodes1, nodes2:
            gathered = asyncio.get_event_loop().run_until_complete(
                asyncio.gather(*(node.close() for node in nodeset)))
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


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-H", "--hostname", default=None)
    parser.add_argument("-U", "--username", default=None)
    parser.add_argument("-n", "--number", default=10, type=int)
    parser.add_argument("-t", "--timeout", default=1., type=float)
    parser.add_argument("-s", "--share-connection", action='store_false',
                        default=True)
    args = parser.parse_args()

    Tests().simple(hostname=args.hostname,
                 username=args.username,
                 number=args.number,
                 share_connection=args.share_connection)

if __name__ == '__main__':
    main()

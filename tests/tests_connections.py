# pylint: disable=c0111

import asyncio

from unittest import TestCase

from asynciojobs import Scheduler

from apssh import SshNode, SshJob, ColonFormatter

from .util import localuser, in_out_connections

class Tests(TestCase):

    def simple(self, hostname='localhost', username=None,
               *, share_connection=False, number=5):
        """
        one node 1 hop away
        create one or <number> connections (depending on share_connection)
        and run <number> times 'echo simple{i}'
        check the number of alive connections
        """
        if username is None:
            username = localuser()

        connections = number if not share_connection else 1

        print(f"creating {number} commands on {connections} connections"
              f" to {username}@{hostname}")
        scheduler = Scheduler()
        nodes = []
        jobs = []
        for i in range(number):
            if share_connection:
                if i == 0:
                    node = SshNode(hostname, username=username,
                                   formatter=ColonFormatter(verbose=False))
                    nodes.append(node)
                else:
                    pass
            else:
                node = SshNode(hostname, username=username,
                               formatter=ColonFormatter(verbose=False))
                nodes.append(node)
            jobs.append(SshJob(node=node,
                               command=f'echo simple{i}',
                               scheduler=scheduler))

        # record base status
        in0, out0 = in_out_connections()
        print(f"INITIAL count in={in0} out={out0}")

        scheduler.run()

        in1, out1 = in_out_connections()
        print(f"AFTER RUN in={in1} out={out1}")
        self.assertEqual(in1-in0, connections)
        self.assertEqual(out1-out0, connections)

        # cleanup
        gathered = asyncio.get_event_loop().run_until_complete(
            asyncio.gather(*(node.close() for node in nodes)))
        in1, out1 = in_out_connections()
        print(f"AFTER CLEANUP in={in1} out={out1}")
        self.assertEqual(in1-in0, 0)
        self.assertEqual(out1-out0, 0)

    def test_simple_1(self):
        self.simple(share_connection=True)

    def test_simple_n(self):
        self.simple(share_connection=False)

    def hop2(self, hostname='localhost', username=None,
             *, share_connection=False, number=5):
        """
        same but with 2 hops
        create either one or <number> level1 connections (depending on share_connection)
        then <number> times, create a 2-hop connection (ditto)
        and on each of these, run 'hostname'
        check the number of alive connections
        """
        pass


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

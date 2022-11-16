"""
the bulk of the tests for apssh
"""

# pylint: disable=c0111,c0103,r0904,w0106, unspecified-encoding

import unittest

from pathlib import Path
import string
import random

from asynciojobs import Scheduler, Sequence

from apssh import SshNode, SshJob, LocalNode
from apssh import Run, RunScript, RunString, Push, Pull
from apssh import load_private_keys

from apssh import HostFormatter, CaptureFormatter

from apssh.cli import Apssh

from .util import localuser, localhostname

class Tests(unittest.TestCase):

    def localnode(self, capture=False, username=None):
        formatter = HostFormatter() if not capture else CaptureFormatter()
        return SshNode(hostname='localhost',
                       username=username or localuser(),
                       # this is the default in fact
                       keys=load_private_keys(),
                       formatter=formatter)

    # all the ways to create a simple command

    def run_one_job(self, job, *, details=False, expected=True):
        print(job)
        scheduler = Scheduler(job, verbose=True)
        orchestration = scheduler.run()
        scheduler.list(details=details)
        if not orchestration:
            scheduler.debrief()
        self.assertTrue(orchestration)
        if expected:
            self.assertEqual(job.result(), 0)
        else:
            self.assertNotEqual(job.result(), 0)

    # is the local box properly configured ?
    def test_local_users(self):
        self.run_one_job(SshJob(node=self.localnode(username="root"), command="id"))
        self.run_one_job(SshJob(node=self.localnode(username="apsshuser"), command="id"))


    # singular command =
    def test_s1(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   command=["echo", "SshJob with s1 command singular",
                            "$(hostname)"],
                   label='s1'))

    def test_s2(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   command=Run(
                       "echo", "SshJob with s2 command singular", "$(hostname)"
                       ),
                   label='s2'))

    def test_s3(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   command=[
                       Run("echo", "SshJob with s3 command singular",
                           "$(hostname)")],
                   label='s3'))

    def test_s4(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   command="echo SshJob with s4 command singular $(hostname)",
                   label='s4'))

    # plural commands =
    def test_p1(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   commands=[
                       "echo", "SshJob p1 commands plural", "$(hostname)"],
                   label='p1'))

    def test_p2(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   commands=Run(
                       "echo", "SshJob p2 commands plural", "$(hostname)"),
                   label='p2'))

    def test_p3(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   commands=[Run(
                       "echo", "SshJob p3 commands plural", "$(hostname)")],
                   label='p3'))

    def test_p4(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   commands="echo SshJob with p4 commands plural $(hostname)",
                   label='p4'))

    # RunScript stuff
    def test_local_script(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   command=RunScript("tests/script.sh"),
                   label='script'))

    def test_local_script_includes(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   command=RunScript("tests/needsinclude.sh",
                                     includes=["tests/inclusion.sh"]),
                   label='script_includes'))

    def test_local_script_args(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   command=RunScript(
                       "tests/script-with-args.sh", "foo", "bar", "tutu"),
                   label='script'))

    # mixing stuff
    def test_mixed_commands(self):
        includes = ["tests/inclusion.sh"]
        self.run_one_job(
            SshJob(node=self.localnode(),
                   commands=[
                       RunScript("tests/needsinclude.sh",
                                 "run1", includes=includes),
                       Run("echo +++++; cat /etc/lsb-release; echo +++++"),
                       RunScript("tests/needsinclude.sh", "another",
                                 "run", includes=includes)
                   ],
                   label='script_commands'))

    ##########
    # NOTE
    # we are cheating here, and open tests/script-with-args.sh
    # for reading a string that has a script...

    def test_local_string(self):
        with open("tests/script-with-args.sh") as reader:
            my_script = reader.read()
        self.run_one_job(
            SshJob(node=self.localnode(),
                   command=RunString(my_script, "foo", "bar", "tutu"),
                   label="test_local_string"))

    def test_local_string_includes(self):
        with open("tests/needsinclude.sh") as reader:
            my_script = reader.read()
        self.run_one_job(
            SshJob(node=self.localnode(),
                   command=RunString(my_script, "some", "'more text'",
                                     remote_name="run-script-sample.sh",
                                     includes=["tests/inclusion.sh"]),
                   label="test_local_string"))

    ##########
    def test_capture(self):
        node = self.localnode(capture=True)
        self.run_one_job(
            SshJob(node=node,
                   command="hostname",
                   label='capture'))

        self.assertEqual(node.formatter.get_capture(),
                         f"{localhostname()}\n")

    def test_logic1(self):
        self.run_one_job(
            SshJob(node=self.localnode(),
                   critical=False,
                   commands=[Run("false"),
                             Run("true")],
                   label="should fail"),
            expected=False)

    def test_logic2(self):
        todo = SshJob(node=self.localnode(),
                      commands=[Run("true"),
                                Run("false")],
                      label="should fail")
        sched = Scheduler(todo, critical=False, verbose=True)
        self.assertFalse(sched.run())

    def random_file(self, name, size):
        with open(name, "w") as output:
            for _ in range(2**size):
                output.write(random.choice(string.ascii_lowercase))

    ##########
    def test_file_loopback(self, size=20):
        # randomly create a 2**size chars file
        b1 = f"random-{size}"
        b2 = f"loopback-{size}"
        b3 = f"again-{size}"
        p1 = "tests/" + b1
        p2 = "tests/" + b2
        p3 = "tests/" + b3
        self.random_file(p1, size)

        self.run_one_job(
            SshJob(node=self.localnode(),
                   commands=[
                       Run("mkdir -p apssh-tests"),
                       Push(localpaths=p1, remotepath="apssh-tests"),
                       Pull(remotepaths="apssh-tests/" +
                            b1, localpath="tests/" + b2),
                   ]))

        with open(p1) as f1:
            s1 = f1.read()

        with open(p2) as f2:
            s2 = f2.read()
            self.assertEqual(s1, s2)

        # pull it again in another ssh connection
        self.run_one_job(
            SshJob(node=self.localnode(),
                   commands=[
                       Run("mkdir -p apssh-tests"),
                       Pull(remotepaths="apssh-tests/" +
                            b1, localpath="tests/" + b3),
                   ]))
        with open(p3) as f3:
            s3 = f3.read()
            self.assertEqual(s1, s3)

    def test_local_command(self):
        # create random file in python rather than with /dev/random
        # this uses sha1sum which is available on the linux test boxes
        # but not in macos
        random_full = "RANDOM-full"
        random_head = "RANDOM"

        self.random_file(random_full, size=19)
        print("DONE")
        self.run_one_job(
            # details = True,
            job=SshJob(
                node=LocalNode(),
                commands=[
                    Run(f"head -c {2**18} < {random_full} > {random_head}"),
                    Run(f"ls -l {random_head}"),
                    Run(f"sha1sum {random_head}"),
                ]))

    def test_local_command2(self):
        self.run_one_job(
            # details = True,
            job=SshJob(
                node=LocalNode(),
                commands=[
                    Run("for i in $(seq 3); do echo line $i; sleep 1; done"),
                ]))

    def test_commands_verbose(self):
        dummy_path = "tests/dummy-10"
        dummy_file = Path(dummy_path).name
        scheduler = Scheduler()
        Sequence(
            SshJob(
                node=self.localnode(),
                verbose=True,
                commands=[
                    Run("hostname"),
                    RunScript("tests/script-with-args.sh", "arg1", "arg2"),
                    RunString("for i in $(seq 3); do echo verbose$i; done"),
                    Push(localpaths=dummy_path, remotepath="."),
                    Pull(remotepaths=dummy_file,
                         localpath=dummy_path + ".loop"),
                ]),
            SshJob(
                node=LocalNode(),
                critical=True,
                commands=Run("diff {x} {x}.loop".format(x=dummy_path),
                             verbose=True)),
            scheduler=scheduler)
        ok = scheduler.run()
        ok or scheduler.debrief()
        self.assertTrue(ok)

    def test_x11(self):
        self.run_one_job(
            job=SshJob(
                node=self.localnode(),
                commands=[
                    Run("echo DISPLAY=$DISPLAY", x11=True),
                    Run("xlsfonts | head -5", x11=True),
                ]))

    def test_x11_shell(self):
        self.run_one_job(
            job=SshJob(
                node=self.localnode(),
                command=[
                    Run("echo DISPLAY=$DISPLAY", x11=True),
                    RunString("""#!/bin/bash
xlsfonts | head -5
""", x11=True)]))

    ##########
    # some variants involving xterm
    # so they will hang, someone needs to type control-d to end them
    # this is why we don't call then test_*

    def _run_xterm_node_shell(self, node, shell):
        if shell:
            xterm_command = RunString("""#!/bin/bash
xterm
""", x11=True)
        else:
            xterm_command = Run("xterm", x11=True)
        self.run_one_job(
            job=SshJob(
                node=node,
                command=[
                    Run("echo without x11, DISPLAY=$DISPLAY"),
                    Run("echo with x11, DISPLAY=$DISPLAY", x11=True),
                    xterm_command,
                    ]))

    # on faraday
    def xterm_1hop(self):
        self._run_xterm_node_shell(self.localnode(), False)

    def xterm_1hop_shell(self):
        self._run_xterm_node_shell(self.localnode(), True)

    # fit23 must be turned on
    def node_2hops(self):
        return SshNode(hostname="localhost",
                       username=localuser(),
                       gateway=self.localnode())

    def xterm_2hops(self):
        self._run_xterm_node_shell(self.node_2hops(), False)

    def xterm_2hops_shell(self):
        self._run_xterm_node_shell(self.node_2hops(), True)

    def run_apssh(self, command_line_as_list):
        apssh = Apssh()
        exitcode = apssh.main(*command_line_as_list)
        self.assertEqual(exitcode, 0)
        return apssh

    def test_targets1(self):
        argv = []
        argv = ['-l', localuser()]
        argv += ['-t', 'localhost']
        argv += ['hostname']
        self.run_apssh(argv)

    def test_targets2(self):
        argv = []
        argv = ['-l', localuser()]
        argv += ['-t', "localhost"]
        argv += ['-t', "127.0.0.1"]
        argv += ['hostname']
        self.run_apssh(argv)

    def test_targets3(self):
        filename = 'TARGETS3'
        with open(filename, 'w') as targets:
            targets.write(f'{localuser()}@localhost\n')
            targets.write(f'{localuser()}@127.0.0.1\n')
        argv = []
        argv += ['-t', filename]
        argv += ['hostname']
        self.run_apssh(argv)

    def test_targets4(self):
        filename = 'TARGETS4'
        with open(filename, 'w') as targets:
            targets.write(f'{localuser()}@localhost\n')
            targets.write(f'{localuser()}@127.0.0.1\n')
        argv = []
        argv += ['-l', localuser()]
        argv += ['-t', filename]
        argv += ['hostname']
        self.run_apssh(argv)

    # this is one form used on r2lab, e.g. when doing map
    # on the selected nodes
    def test_targets5(self):
        argv = []
        argv += ['-l', localuser()]
        argv += ['-t', "localhost 127.0.0.1"]
        argv += ['hostname']
        self.run_apssh(argv)

    def test_targets6(self):
        folder = Path("TARGETS-DIR")
        folder.mkdir(exist_ok=True)
        names = ['localhost', '127.0.0.1']
        for name in names:
            with (folder / name).open('w'):
                pass
        argv = []
        argv += ['-l', "apsshuser"]
        argv += ['-t', str(folder)]
        argv += ['id']
        self.run_apssh(argv)

    # gwt = gateway-related targets
    def test_gwt1(self):
        argv = []
        argv += ['-t', "localhost"]
        argv += ['id']
        apssh = self.run_apssh(argv)
        self.assertEqual(apssh.proxies[0].gateway, None)
        self.assertEqual(apssh.proxies[0].hostname, "localhost")
        self.assertEqual(apssh.proxies[0].username, localuser())

    def test_gwt2(self):
        argv = []
        argv += ['-t', "localhost"]
        argv += ['-l', "apsshuser"]
        argv += ['id']
        apssh = self.run_apssh(argv)
        self.assertEqual(apssh.proxies[0].gateway, None)
        self.assertEqual(apssh.proxies[0].hostname, "localhost")
        self.assertEqual(apssh.proxies[0].username, "apsshuser")

    def test_gwt3(self):
        argv = []
        argv += ['-t', "localhost"]
        argv += ['-g', "127.0.0.1"]
        argv += ['--debug']
        argv += ['id']
        apssh = self.run_apssh(argv)
        self.assertEqual(apssh.proxies[0].gateway.hostname, "127.0.0.1")
        self.assertEqual(apssh.proxies[0].gateway.username, localuser())
        self.assertEqual(apssh.proxies[0].hostname, "localhost")
        self.assertEqual(apssh.proxies[0].username, localuser())

    def test_gwt4(self):
        argv = []
        argv += ['-t', "localhost"]
        argv += ['-l', "apsshuser"]
        argv += ['-g', "127.0.0.1"]
        argv += ['id']
        apssh = self.run_apssh(argv)
        self.assertEqual(apssh.proxies[0].gateway.hostname, "127.0.0.1")
        self.assertEqual(apssh.proxies[0].gateway.username, "apsshuser")
        self.assertEqual(apssh.proxies[0].hostname, "localhost")
        self.assertEqual(apssh.proxies[0].username, "apsshuser")

    def test_gwt5(self):
        argv = []
        argv += ['-t', "root@localhost"]
        argv += ['-g', "root@127.0.0.1"]
        argv += ['id']
        apssh = self.run_apssh(argv)
        self.assertEqual(apssh.proxies[0].gateway.hostname, "127.0.0.1")
        self.assertEqual(apssh.proxies[0].gateway.username, "root")
        self.assertEqual(apssh.proxies[0].hostname, "localhost")
        self.assertEqual(apssh.proxies[0].username, "root")

    def test_gwt6(self):
        argv = []
        argv += ['-t', "127.0.0.1,127.0.0.3->127.0.0.2"]
        argv += ['id']
        apssh = self.run_apssh(argv)
        self.assertEqual(apssh.proxies[0].gateway, None)
        self.assertEqual(apssh.proxies[0].hostname, "127.0.0.1")
        self.assertEqual(apssh.proxies[0].username, localuser())

        self.assertEqual(apssh.proxies[1].gateway.hostname, "127.0.0.3")
        self.assertEqual(apssh.proxies[1].gateway.username, localuser())
        self.assertEqual(apssh.proxies[1].hostname, "127.0.0.2")
        self.assertEqual(apssh.proxies[1].username, localuser())

    def test_gwt7(self):
        argv = []
        argv += ['-t', "127.0.0.1 127.0.0.3->127.0.0.2"]
        argv += ['-g', "apsshuser@127.0.0.10"]
        argv += ['id']
        apssh = self.run_apssh(argv)
        self.assertEqual(apssh.proxies[0].gateway.hostname, "127.0.0.10")
        self.assertEqual(apssh.proxies[0].gateway.username, "apsshuser")
        self.assertEqual(apssh.proxies[0].hostname, "127.0.0.1")
        self.assertEqual(apssh.proxies[0].username, localuser())

        self.assertEqual(apssh.proxies[1].gateway.hostname, "127.0.0.3")
        self.assertEqual(apssh.proxies[1].gateway.username, localuser())
        self.assertEqual(apssh.proxies[1].hostname, "127.0.0.2")
        self.assertEqual(apssh.proxies[1].username, localuser())

    def test_gwt8(self):
        argv = []
        # this would mean use a direct connection for the first node
        argv += ['-t', "None->127.0.0.1 127.0.0.3->127.0.0.2"]
        argv += ['-g', "apsshuser@127.0.0.10"]
        argv += ['id']
        apssh = self.run_apssh(argv)
        self.assertEqual(apssh.proxies[0].gateway, None)
        self.assertEqual(apssh.proxies[0].hostname, "127.0.0.1")
        self.assertEqual(apssh.proxies[0].username, localuser())

        self.assertEqual(apssh.proxies[1].gateway.hostname, "127.0.0.3")
        self.assertEqual(apssh.proxies[1].gateway.username, localuser())
        self.assertEqual(apssh.proxies[1].hostname, "127.0.0.2")
        self.assertEqual(apssh.proxies[1].username, localuser())

    def test_gwt9(self):
        argv = []
        # this would mean use a direct connection for the first node
        argv += ['-t', "None→127.0.0.1 127.0.0.3→127.0.0.2"]
        argv += ['-g', "apsshuser@127.0.0.10"]
        argv += ['id']
        apssh = self.run_apssh(argv)
        self.assertEqual(apssh.proxies[0].gateway, None)
        self.assertEqual(apssh.proxies[0].hostname, "127.0.0.1")
        self.assertEqual(apssh.proxies[0].username, localuser())

        self.assertEqual(apssh.proxies[1].gateway.hostname, "127.0.0.3")
        self.assertEqual(apssh.proxies[1].gateway.username, localuser())
        self.assertEqual(apssh.proxies[1].hostname, "127.0.0.2")
        self.assertEqual(apssh.proxies[1].username, localuser())

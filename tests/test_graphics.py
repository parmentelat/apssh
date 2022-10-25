"""
Testing basic functions of apssh
"""

# pylint: disable=c0103

import unittest

from asynciojobs import Scheduler, Sequence

from apssh import SshNode, SshJob, Run, RunString, RunScript, Push, Pull

from apssh import Variables, Deferred

from apssh import topology_as_pngfile

from .util import localhostname, localuser, produce_svg

class Tests(unittest.TestCase):

    def test_graphics1(self):

        scheduler = Scheduler(critical=False)

        gateway = SshNode(hostname=localhostname(),
                          username=localuser())

        Sequence(
            SshJob(
                node=gateway,
                command='hostname',
            ),
            SshJob(
                node=gateway,
                command=[
                    Run('ls /etc/passwd'),
                    Run('wc -l /etc/passwd'),
                ]),
            SshJob(
                node=gateway,
                commands=[
                    RunString("#!/usr/bin/env bash\n"
                              "echo with RunString on $(hostname) at $(date)"),
                ]),
            SshJob(
                node=gateway,
                commands=[
                    RunScript("tests/testbasic.sh"),
                ]),
            SshJob(
                node=gateway,
                commands=[
                    Run('wc -l /etc/passwd'),
                    RunString("#!/usr/bin/env bash\n"
                              "echo with RunsString on $(hostname) at $(date)",
                              remote_name="show-host-date"),
                    RunScript("tests/testbasic.sh"),
                ]),
            SshJob(
                node=gateway,
                commands=[
                    RunString("#!/usr/bin/env bash\n"
                              "echo first arg is $1\n",
                              10)
                ]),
            SshJob(
                node=gateway,
                commands=[
                    RunString("#!/usr/bin/env bash\n"
                              "echo first arg is $1\n",
                              10,
                              remote_name='short-show-args')
                ]),
            SshJob(
                node=gateway,
                commands=[
                    RunString("#!/usr/bin/env bash\n"
                              "echo first arg is $1\n"
                              "echo second arg is $2\n"
                              "echo third arg is $3\n"
                              "echo fourth arg is $4\n",
                              100, 200, 300, 400)
                ]),
            SshJob(
                node=gateway,
                commands=[
                    RunString("#!/usr/bin/env bash\n"
                              "echo first arg is $1\n"
                              "echo second arg is $2\n"
                              "echo third arg is $3\n"
                              "echo fourth arg is $4\n",
                              1000, 2000, 3000, 4000,
                              remote_name='long-show-args')
                ]),
            SshJob(
                node=gateway,
                commands=[
                    RunString("#!/usr/bin/env bash\n"
                              "echo first arg is $1\n"
                              "echo second arg is $2\n"
                              "echo third arg is $3\n"
                              "echo fourth arg is $4\n",
                              1000, 2000, 3000, 4000,
                              remote_name='long-show-args',
                              label='snip')
                ]),
            SshJob(
                node=gateway,
                commands=[
                    Run("hostname", label="Run()"),
                    RunScript("foobar", label="RunScript()"),
                    RunString("foobar", label="RunString()"),
                    Push("foobar", remotepath="remote", label="Push()"),
                    Pull("remote", localpath="foobar", label="Pull()"),
                    Run("hostname", label=None),
                    RunScript("foobar", label=[]),
                    RunString("foobar", label=0),
                    Push("foobar", remotepath="remote", label={}),
                    Pull("remote", localpath="foobar", label=""),
                ]),
            scheduler=scheduler,
        )

        print("NO DETAILS")
        scheduler.list()
        print("WITH DETAILS")
        scheduler.list(details=True)
        produce_svg(scheduler, "test_graphics1")

        ok = scheduler.run()

        self.assertFalse(ok)


    def test_topology(self):
        g1 = SshNode("faraday", username="inria_tutorial")
        n1 = SshNode(gateway=g1, hostname="fit01", username="root")
        n2 = SshNode(gateway=g1, hostname="fit02", username="root")

        s = Scheduler()
        SshJob(n1, command='hostname', scheduler=s)
        SshJob(n2, command='hostname', scheduler=s)

        topology_as_pngfile(s, "topology")

    def test_variables(self):
        """
        check how variables are rendered
        """
        v1 = Variables()
        v2 = Variables()
        v2.defined = 'OK-defined'

        template = "defined: {{defined}} undefined: {{undefined}}"

        scheduler = Scheduler(critical=False)

        gateway = SshNode(hostname=localhostname(),
                          username=localuser())

        Sequence(
            SshJob(gateway,
                   command=Deferred(template, v1)),
            SshJob(gateway,
                   command=Deferred(template, v2)),
            scheduler=scheduler)

        produce_svg(scheduler, "test_graphics_variables")

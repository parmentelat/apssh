import unittest

from asynciojobs import Scheduler, Sequence

from apssh import SshNode, SshJob, Run, RunString, RunScript

class TestBasic(unittest.TestCase):

    def test_basic(self):

        scheduler = Scheduler()

        gateway = SshNode(hostname='faraday.inria.fr', username='root')

        Sequence (
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
                              "echo with RunsString on $(hostname) at $(date)"),
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
                              10
                    )
            ]),
            SshJob(
                node=gateway,
                commands=[
                    RunString("#!/usr/bin/env bash\n"
                              "echo first arg is $1\n",
                              10,
                              remote_name = 'short-show-args'
                    )
            ]),
            SshJob(
                node=gateway,
                commands=[
                    RunString("#!/usr/bin/env bash\n"
                              "echo first arg is $1\n"
                              "echo second arg is $2\n"
                              "echo third arg is $3\n"
                              "echo fourth arg is $4\n",
                              100, 200, 300, 400
                    )
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
                              remote_name = 'long-show-args'
                    )
            ]),
            scheduler=scheduler,
        )

        scheduler.export_as_dotfile('tests/testbasic.dot')

        ok = scheduler.run()

        self.assertTrue(ok)

if __name__ == '__main__':
    unittest.main()

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
                    RunString("#!/usr/bin/env bash\necho with RunsString on $(hostname) at $(date)"),
                ]),
            SshJob(
                node=gateway,
                commands=[
                    RunScript("tests/testbasic.sh"),
                ]),
            scheduler=scheduler,
        )

        scheduler.export_as_dotfile('tests/testbasic.dot')

        ok = scheduler.run()

        self.assertTrue(ok)

if __name__ == '__main__':
    unittest.main()

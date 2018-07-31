# pylint: disable=c0111

import unittest

from asynciojobs import Scheduler

from apssh import SshJob, LocalNode, Run, RunScript, RunString, SshNode
from apssh import ColonFormatter, load_private_keys, CommandFailedError

#from apssh.util import co_close_ssh_from_sched

from . import util
#from . import utilps

class Tests(unittest.TestCase):

    def test_allowed_exits(self, host="localhost", username=None,
                           wait_time=2, tested_sig="TERM"):
        print("Testing that we do not have exceptions on critical "
              "jobs uppon receiving a signal if this one has been "
              "whitelisted")
        if username is None:
            username = util.localuser()
        received_exception = False
        scheduler = Scheduler()

        node = SshNode(host, username=username)

        job = [SshJob(node=node, forever=True,
                      command=[Run(f"sleep {wait_time*15}",
                                   allowed_exits=[f"{tested_sig}"]
                                   )
                               ]
                      )
               ]
        service = Scheduler(*job, scheduler=scheduler)
        job_sleep = SshJob(node=node, scheduler=scheduler,
                           command=Run(f"sleep {wait_time}"))
        jobkill = SshJob(node=node, required=job_sleep, scheduler=scheduler,
                         # Use kill $(pgrep) instead of pkill
                         # because cursiously pkill does not return
                         # an exit code nor an exit signal
                         command=Run(f"kill -{tested_sig} $(pgrep sleep)")
                         )
        try:
            scheduler.orchestrate()
        except CommandFailedError:
            received_exception = True
        self.assertFalse(received_exception)

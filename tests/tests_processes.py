import unittest

import os
import time
import asyncio
import signal
from pathlib import Path

from asynciojobs import Scheduler

from apssh import SshJob, LocalNode, Run, RunScript, RunString, SshNode
from apssh import ColonFormatter, load_private_keys, CommandFailedError
#from apssh.util import co_close_ssh_from_sched

from . import util
from . import utilps

class Tests(unittest.TestCase):

    def get_files_len_and_alive(self, node):
        apssh_path = "/root"
        if isinstance(node, LocalNode):
            apssh_path = "."
        file_start = util.get_apssh_files_list(apssh_path)
        expected_alive = util.check_apssh_files_alive(file_start)
        return len(file_start), expected_alive

    def init_scheduler(self, scheduler, nested=False, jobs=[],
                       sched_timeout=None, diff_sched=False):
        if nested:
            if not diff_sched:
                n_sched = [Scheduler(*jobs)]
            else:
                n_sched = [Scheduler(job, forever=True) for job in jobs]
            for s in n_sched:
                scheduler.add(s)
        else:
            for job in jobs:
                scheduler.add(job)
        if sched_timeout is not None:
            scheduler.timeout = sched_timeout
        return scheduler

    def scheduler_run(self, command_object, host="localhost",
                      username=None, timeout=2, node=LocalNode(),
                      nested=False, sched_timeout=None, diff_sched=False,
                      expected_diff=0):

        expected_len, expected_alive = self.get_files_len_and_alive(node)
        if username is None:
            username = util.localuser()

        scheduler = Scheduler()
        command = command_object
        jobs = [SshJob(node=node,
                       forever=True, command=command),
                SshJob(node=node,
                       command=[#Run("echo \"toto\""),
                                Run("sleep {}".format(abs(timeout/2))),
                                Run("sleep {}".format(timeout/2))
                                ])
                ]
        scheduler = self.init_scheduler(scheduler, nested=nested, jobs=jobs,
                                        sched_timeout=sched_timeout,
                                        diff_sched=diff_sched)
        pm = utilps.ProcessMonitor()
        ssh_fam = pm.ssh_family()
        scheduler.export_as_pngfile("debug")
        #print("_________________________________________________PRE LEN : {}".format(len(ssh_fam)))
        try:
            scheduler.run()
        except TimeoutError:
            print("Timeout Error")
        except CommandFailedError:
            print("Command failed")

        if sched_timeout:
            time.sleep(2*sched_timeout)
        pm.reset()
        lssh_famp = pm.ssh_family()
        #Sometime there is a remnant with PS of the non service command
        diff = len(lssh_famp) - len(ssh_fam)
        #for pid in lssh_famp:
        #    cmdline = psutil.Process(pid).cmdline()
        #    print(cmdline)
        #    if (pid not in ssh_fam
        #        and cmdline[0] == 'sleep'
        #        and cmdline[1] == "{}".format(timeout/2)):
        #        expected_diff += 1
        #print("_________________________________________________POST LEN : {}".format(len(ssh_fam)))
        len_file, alive = self.get_files_len_and_alive(node)
        self.assertEqual(alive, expected_alive,
                         f"expected {expected_alive} alive processes")
        self.assertEqual(len_file, expected_len,
                         f"expected {expected_len} files in .apssh")
        self.assertEqual(diff, expected_diff,
                         f"expected a ssh family count of {expected_diff}")
    def test_remote_implicit_timeout_Run(self, host="localhost", username=None,
                                timeout=4):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on remote nodes "
              "and timing out")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = Run("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node,
                           sched_timeout=timeout/2, expected_diff=2)

    def test_remote_nested_implicit_timeout_Run(self, host="localhost",
                                                username=None, timeout=4):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on remote nodes "
              "and timing out")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = Run("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, sched_timeout=timeout/2,
                           nested=True, expected_diff=2)

    def test_remote_para_nested_implicit_timeout_Run(self, host="localhost",
                                                     username=None, timeout=4):
        print("Testing that implicit shutdown on parallel nested scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on remote nodes "
              "and timing out")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = Run("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, sched_timeout=timeout/2,
                           nested=True, diff_sched=True, expected_diff=1)

    def test_remote_implicit_timeout_RunScript(self, host="localhost",
                                               username=None,
                                               timeout=4):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of RunScript type on remote nodes "
              "and timing out")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunScript("tests/aservice.sh", 10*timeout, service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node,
                           sched_timeout=timeout/2, expected_diff=2)

    def test_remote_nested_implicit_timeout_RunScript(self, host="localhost",
                                               username=None,
                                               timeout=4):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunScript type on remote nodes "
              "and timing out")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunScript("tests/aservice.sh", 10*timeout, service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node,
                           sched_timeout=timeout/2, nested=True,
                           expected_diff=1)

    def test_remote_para_nested_implicit_timeout_RunScript(self,
                                                           host="localhost",
                                                           username=None,
                                                           timeout=4):
        print("Testing that implicit shutdown on parallel scheduler "
              "does not leave Zombie processes "
              "when using a command of RunScript type on remote nodes "
              "and timing out")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunScript("tests/aservice.sh", 10*timeout, service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, sched_timeout=timeout/2,
                           nested=True, diff_sched=True, expected_diff=1)

    def test_remote_implicit_timeout_RunString(self, host="localhost",
                                               username=None, timeout=4):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of RunString type on remote nodes "
              "and timing out")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunString("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node,
                           sched_timeout=timeout/2, expected_diff=2)

    def test_remote_nested_implicit_timeout_RunString(self, host="localhost",
                                                      username=None, timeout=4):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunString type on remote nodes "
              "and timing out")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunString("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, sched_timeout=timeout/2,
                           nested=True, expected_diff=1)

    def test_remote_para_nested_implicit_timeout_RunString(self,
                                                           host="localhost",
                                                           username=None,
                                                           timeout=4):
        print("Testing that implicit shutdown on parallel nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunString type on remote nodes "
              "and timing out")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunString("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, sched_timeout=timeout/2,
                           nested=True, diff_sched=True, expected_diff=1)

    def test_implicit_exception_Run(self, host="localhost", username=None,
                                timeout=-2):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on remote nodes "
              "and exiting uppon exception")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = Run("sleep {}".format(10*abs(timeout)), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, expected_diff=2)

    def test_implicit_nested_exception_Run(self, host="localhost",
                                           username=None, timeout=-2):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on remote nodes "
              "and exiting uppon exception")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = Run("sleep {}".format(10*abs(timeout)), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           expected_diff=2)

    def test_implicit_para_nested_exception_Run(self, host="localhost",
                                                username=None, timeout=-2):
        print("Testing that implicit shutdown on parallel nested scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on remote nodes "
              "and exiting uppon exception")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = Run("sleep {}".format(10*abs(timeout)), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           diff_sched=True, expected_diff=2)

    def test_implicit_exception_RunScript(self, host="localhost", username=None,
                                          timeout=-2):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of RunScript type on remote nodes "
              "and exiting uppon exception")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunScript("tests/aservice.sh", 10*abs(timeout),
                            service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, expected_diff=2)

    def test_implicit_nested_exception_RunScript(self, host="localhost",
                                                 username=None, timeout=-2):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunScript type on remote nodes "
              "and exiting uppon exception")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunScript("tests/aservice.sh", 10*abs(timeout),
                            service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           expected_diff=2)

    def test_implicit_para_nested_exception_RunScript(self, host="localhost",
                                                      username=None,
                                                      timeout=-2):
        print("Testing that implicit shutdown on parallel nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunScript type on remote nodes "
              "and exiting uppon exception")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunScript("tests/aservice.sh", 10*abs(timeout),
                            service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           diff_sched=True, expected_diff=2)

    def test_implicit_exception_RunString(self, host="localhost", username=None,
                                          timeout=-2):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of RunString type on remote nodes "
              "and exiting uppon exception")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunString("sleep {}".format(10*abs(timeout)), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, expected_diff=2)

    def test_implicit_nested_exception_RunString(self, host="localhost",
                                                 username=None,
                                                 timeout=-2):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunString type on remote nodes "
              "and exiting uppon exception")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunString("sleep {}".format(10*abs(timeout)), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           expected_diff=2)

    def test_implicit_para_nested_exception_RunString(self, host="localhost",
                                                      username=None,
                                                      timeout=-2):
        print("Testing that implicit shutdown on parallel nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunString type on remote nodes "
              "and exiting uppon exception")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunString("sleep {}".format(10*abs(timeout)), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           diff_sched=True, expected_diff=2)



    def test_remote_Run(self, host="localhost", username=None, timeout=2):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on remote nodes")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = Run("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, expected_diff=2)

    def test_nested_remote_Run(self, host="localhost", username=None,
                                timeout=2):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on remote nodes")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = Run("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           expected_diff=2)

    def test_para_nested_remote_Run(self, host="localhost", username=None,
                                timeout=2):
        print("Testing that implicit shutdown on parallel nested scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on remote nodes")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = Run("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           diff_sched=True, expected_diff=2)

    def test_remote_RunScript(self, host="localhost", username=None,
                            timeout=2):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of RunScript type on remote nodes")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunScript("tests/aservice.sh", timeout*10, service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, expected_diff=2)

    def test_nested_remote_RunScript(self, host="localhost",
                                               username=None, timeout=2):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunScript type on remote nodes")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunScript("tests/aservice.sh", timeout*10, service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           expected_diff=2)

    def test_para_nested_remote_RunScript(self, host="localhost",
                                               username=None, timeout=2):
        print("Testing that implicit shutdown on parallel nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunScript type on remote nodes")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunScript("tests/aservice.sh", timeout*10, service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           diff_sched=True, expected_diff=2)

    def test_remote_RunString(self, host="localhost", username=None,
                            timeout=2):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of RunString type on remote nodes")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunString("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, expected_diff=2)

    def test_nested_remote_RunString(self, host="localhost",
                                               username=None, timeout=2):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunString type on remote nodes")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunString("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           expected_diff=2)

    def test_para_nested_remote_RunString(self, host="localhost",
                                               username=None, timeout=2):
        print("Testing that implicit shutdown on parallel nested scheduler "
              "does not leave Zombie processes "
              "when using a command of RunString type on remote nodes")
        node = SshNode(host, username=username,
                                      formatter=ColonFormatter(verbose=False))
        command = RunString("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           diff_sched=True, expected_diff=2)

    def test_local_Run(self, host="localhost", username=None,
                                timeout=2):
        print("Testing that implicit shutdown on scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on local node")
        node = LocalNode()
        command = Run("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, expected_diff=0)

    def test_nested_local_Run(self, host="localhost", username=None,
                                timeout=2):
        print("Testing that implicit shutdown on nested scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on local node")
        node = LocalNode()
        command = Run("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           expected_diff=0)

    def test_para_nested_local_Run(self, host="localhost", username=None,
                                timeout=2):
        print("Testing that implicit shutdown on parallel nested scheduler "
              "does not leave Zombie processes "
              "when using a command of Run type on local node")
        node = LocalNode()
        command = Run("sleep {}".format(1000*timeout), service=True)
        self.scheduler_run(command, host=host, username=username,
                           timeout=timeout, node=node, nested=True,
                           diff_sched=True, expected_diff=0)
    ##### xxx Possible to run stuff on localnode with RunString and RunScript?
    #def test_local_RunScript(self, host="localhost", username=None,
    #                        timeout=2):
    #    print("Testing that implicit shutdown on scheduler does not leave\
# Zombie processes when using a command of RunScript type on local node")
    #    node = LocalNode()
    #    command = RunScript("tests/aservice.sh", timeout*10, service=True)
    #    self.scheduler_run(command, host=host, username=username,
    #                       timeout=timeout, node=node)
    #def test_local_RunString(self, host="localhost", username=None,
    #                        timeout=2):
    #    print("Testing that implicit shutdown on scheduler does not leave\
# Zombie processes when using a command of RunString type on local node")
    #    node = LocalNode()
    #    command = RunString("sleep {}".format(1000*timeout), service=True)
    #    self.scheduler_run(command, host=host, username=username,
    #                       timeout=timeout, node=node)
    # xxx This one is maybe not a classical use case
    def explicit_connection_close(self, command_object=None,
     host="localhost", username=None, timeout=2, node=LocalNode(),
     nested=False):
        ## For now, always fail since it is not implemented
        print("Check that the call to close_connection do not leave zombies")
        command_object = Run("sleep ", 1000*timeout, service=True)

        if username is None:
            username = util.localuser()

        node = SshNode(host, username=username,
                       formatter=ColonFormatter(verbose=False))

        expected_len, expected_alive = self.get_files_len_and_alive(node)


        async def run_scheduler(scheduler, node):
            await asyncio.wait([scheduler.co_run()], timeout=timeout)
            print("Closing connection")
            ret_close = await co_close_ssh_from_sched(scheduler)
            print("Connection closed")
            self.assertFalse(ret_close)

        scheduler = Scheduler(verbose=False)
        if username is None:
            username = util.localuser()
        scheduler = self.init_scheduler(scheduler, nested=nested,
                                        jobs=[SshJob(node=node, verbose=False,
                                                     forever=True,
                                                     command=command_object)])
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_scheduler(scheduler, node))

        len_file, alive = self.get_files_len_and_alive(node)

        self.assertEqual(alive, expected_alive)
        self.assertEqual(len_file, expected_len)
    def test_service_remote(self, host="localhost", username=None, timeout=2):

        if username is None:
            username = util.localuser()

        async def run_service_remote(timeout, keys, event):

            gremote_node = SshNode(host, username=username,
                                       formatter=ColonFormatter(verbose=False),
                                       keys=keys)
            remote_node = SshNode(host, gateway=gremote_node, username=username,
                                       formatter=ColonFormatter(verbose=False),
                                       keys=keys)
            await remote_node.connect_lazy()
            command = ("echo \"$$\" > .apssh/apssh_spid_11;"
                       "echo \"$$\" > .apssh/apssh_spid_1;"
                       "sleep {}".format(1000*timeout))
            print("Running service")
            await asyncio.wait([remote_node.run(command, command_id='11')],
                               timeout=timeout)
            print("Shutdown service")
            await remote_node.shutdown('11')
            await asyncio.sleep(1)
            event.set()

        async def check_alive_remote(event):
            await event.wait()
            pid = util.get_pid_from_apssh_file("/root/.apssh/apssh_spid_1")
            alive = util.pid_is_alive(pid)
            Path("/root/.apssh/apssh_spid_1").unlink()
            self.assertFalse(alive)
            if not alive:
                print("OK service dead")
            else:
                print("NOK service running")

        print("Testing that run methods of SshNode does not leave Zombie "
              "processes when called directly : ")
        keys = load_private_keys()
        loop = asyncio.get_event_loop()
        event = asyncio.Event()
        #pm = utilps.ProcessMonitor()
        loop.create_task(run_service_remote(timeout, keys, event))
        loop.run_until_complete(check_alive_remote(event))

    # formerly in test_zombie_local.py
    def test_localnode_run(self, timeout=2):
        async def run_service_local_run(timeout, event):
            local_node = LocalNode()

            command = ("echo \"$$\" > .apssh/apssh_spid_11;"
                       "echo \"$$\" > .apssh/apssh_spid_1;"
                       "sleep {}".format(1000*timeout))
            print("Running service")
            await asyncio.wait([local_node.run(command, command_id="11")],
                               timeout=timeout)
            print("Shutdown service")
            await local_node.shutdown("11")
            await asyncio.sleep(1)
            event.set()

        async def check_alive_local_run(event):
            await event.wait()
            pid = util.get_pid_from_apssh_file(".apssh/apssh_spid_1")
            alive = util.pid_is_alive(pid)
            Path(".apssh/apssh_spid_1").unlink()
            self.assertFalse(alive)
            if not alive:
                print("OK service dead")
            else:
                print("NOK service running")
        print("Testing that run methods of localnode does not leave Zombie "
              "processes when called directly : ")
        loop = asyncio.get_event_loop()
        event = asyncio.Event()
        loop.create_task(run_service_local_run(timeout, event))
        loop.run_until_complete(check_alive_local_run(event))

    def tearDownClass():
        # Since we use sleep, if there are an error in one of the test, it is
        # possible that the services finish during another test, generating a
        # false positive
        print("Clean up")
        remaining_processes_local = util.get_apssh_files_list(".")
        remaining_processes_remote = util.get_apssh_files_list("/root")
        path = ".apssh/apssh_spid_*"
        for proc in remaining_processes_local:
            os.kill(-util.get_pid_from_apssh_file(proc), signal.SIGTERM)
            Path(proc).unlink()
            #os.remove(proc)
        for proc in remaining_processes_remote:
            os.kill(-util.get_pid_from_apssh_file(proc), signal.SIGTERM)
            Path(proc).unlink()
        Path(".apssh").rmdir()
        Path("/root/.apssh").rmdir()
            #os.remove(proc)

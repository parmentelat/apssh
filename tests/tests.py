import unittest

import os.path
import string
import random

from asynciojobs import Scheduler, Job, Sequence

from apssh import SshNode, SshJob, LocalNode
from apssh import Run, RunScript, RunString, Push, Pull
from apssh import load_agent_keys

from apssh import TimeColonFormatter, ColonFormatter, CaptureFormatter

class Tests(unittest.TestCase):

    def gateway(self, capture = False):
        formatter = ColonFormatter() if not capture else CaptureFormatter()
        return SshNode(hostname = 'faraday.inria.fr',
                       username = 'root',
                       # this is the default in fact
                       keys=load_agent_keys(),
                       formatter = formatter)
        
    ########## all the ways to create a simple command

    def run_one_job(self, job, details=False):
        scheduler = Scheduler(job, verbose=True)
        orchestration = scheduler.orchestrate()
        scheduler.list(details = details)
        self.assertTrue(orchestration)
        self.assertEqual(job.result(), 0)

    ########## singular command = 
    def test_s1(self):
        self.run_one_job( SshJob(node = self.gateway(),
                                 command = [ "echo", "SshJob with s1 command singular", "$(hostname)" ],
                                 label = 's1'
                             ))
        
    def test_s2(self):
        self.run_one_job( SshJob(node = self.gateway(),
                                 command = Run("echo", "SshJob with s2 command singular", "$(hostname)"),
                                 label = 's2'
                             ))
        
    def test_s3(self):
        self.run_one_job( SshJob(node = self.gateway(),
                                 command = [ Run("echo", "SshJob with s3 command singular", "$(hostname)")] ,
                                 label = 's3'
                             ))
        
    def test_s4(self):
        self.run_one_job( SshJob(node = self.gateway(),
                                 command = "echo SshJob with s4 command singular $(hostname)",
                                 label = 's4'
                             ))
    ########## plural commands =
    def test_p1(self):
        self.run_one_job( SshJob(node = self.gateway(),
                                 commands = [ "echo", "SshJob with p1 commands plural", "$(hostname)" ],
                                 label = 'p1'
                             ))
        
    def test_p2(self):
        self.run_one_job( SshJob(node = self.gateway(),
                                 commands = Run("echo", "SshJob with p2 commands plural", "$(hostname)"),
                                 label = 'p2'
                             ))
        
    def test_p3(self):
        self.run_one_job( SshJob(node = self.gateway(),
                                 commands = [ Run("echo", "SshJob with p3 commands plural", "$(hostname)")] ,
                                 label = 'p3'
                             ))
        
    def test_p4(self):
        self.run_one_job( SshJob(node = self.gateway(),
                                 commands = "echo SshJob with p4 commands plural $(hostname)",
                                 label = 'p4'
                             ))

    ########## RunScript stuff
    def test_local_script(self):
        self.run_one_job(SshJob(node = self.gateway(),
                                command = RunScript("tests/script.sh"),
                                label = 'script'
                            ))
        
    def test_local_script_includes(self):
        self.run_one_job(SshJob(node = self.gateway(),
                                command = RunScript("tests/needsinclude.sh",
                                                      includes = [ "tests/inclusion.sh" ]),
                                label = 'script_includes'
                            ))

    def test_local_script_args(self):
        self.run_one_job(SshJob(node = self.gateway(),
                                command = RunScript("tests/script-with-args.sh", "foo", "bar", "tutu"),
                                label = 'script'
                            ))
        

    ########## mixing stuff
    def test_mixed_commands(self):
        includes = [ "tests/inclusion.sh" ]
        self.run_one_job(SshJob(node = self.gateway(),
                                commands = [
                                    RunScript("tests/needsinclude.sh", "run1", includes = includes),
                                    Run("echo +++++; cat /etc/lsb-release; echo +++++"),
                                    RunScript("tests/needsinclude.sh", "another", "run", includes = includes)
                                ],
                                label = 'script_commands'
                            ))

    ##########
    ### NOTE
    # we are cheating here, and open tests/script-with-args.sh
    # for reading a string that has a script...

    def test_local_string(self):
        with open("tests/script-with-args.sh") as reader:
            my_script = reader.read()
        self.run_one_job(SshJob(node = self.gateway(),
                                command = RunString(my_script, "foo", "bar", "tutu"),
                                label = "test_local_string"))
    
    def test_local_string_includes(self):
        with open("tests/needsinclude.sh") as reader:
            my_script = reader.read()
        self.run_one_job(SshJob(node = self.gateway(),
                                command = RunString(my_script, "some", "'more text'",
                                                    remote_name = "run-script-sample.sh",
                                                    includes = [ "tests/inclusion.sh" ]),
                                label = "test_local_string"))
    
    ########## 
    def test_capture(self):
        node =  self.gateway(capture = True)
        self.run_one_job(SshJob(node = node,
                                command = "hostname",
                                label = 'capture'))

        self.assertEqual(node.formatter.get_capture(),"faraday\n")

    def test_logic1(self):
        self.run_one_job(SshJob(node = self.gateway(),
                                commands = [ Run("false"),
                                             Run("true") ],
                                label = "should succeed"))
        
    def test_logic2(self):
        todo = SshJob(node = self.gateway(),
                      commands = [ Run("true"),
                                   Run("false") ],
                      label = "should fail")
        sched = Scheduler(todo, verbose=True)
        self.assertFalse(sched.orchestrate())

    def random_file(self, name, size):
        with open(name, "w") as output:
            for i in range(2**size):
                output.write(random.choice(string.ascii_lowercase))

    ##########
    def test_file_loopback(self, size=20):
        # randomly create a 2**size chars file
        b1 = "random-{}".format(size)
        b2 = "loopback-{}".format(size)
        b3 = "again-{}".format(size)
        p1 = "tests/" + b1
        p2 = "tests/" + b2
        p3 = "tests/" + b3
        self.random_file(p1, size)

        self.run_one_job(SshJob(node = self.gateway(),
                                commands = [
                                    Run("mkdir -p apssh-tests"),
                                    Push(localpaths = p1, remotepath = "apssh-tests"),
                                    Pull(remotepaths = "apssh-tests/" + b1, localpath = "tests/" + b2),
                                ]))

        with open(p1) as f1:
            s1 = f1.read()

        with open(p2) as f2:
            s2 = f2.read()
            self.assertEqual(s1, s2)
                         
        # pull it again in another ssh connection
        self.run_one_job(SshJob(node = self.gateway(),
                                commands = [
                                    Run("mkdir -p apssh-tests"),
                                    Pull(remotepaths = "apssh-tests/" + b1, localpath = "tests/" + b3),
                                ]))
        with open(p3) as f3:
            s3 = f3.read()
            self.assertEqual(s1, s3)
                         
            
    def test_run_local_command(self):
        self.run_one_job(# details = True,
                         job = SshJob(
                             node = LocalNode(),
                             commands = [
                                 Run("head < /dev/random > RANDOM", "-c", 2**20),
                                 Run("ls -l RANDOM"),
                                 Run("shasum RANDOM"),
                             ]))

    def test_commands_verbose(self):
        dummy_path = "tests/dummy-10"
        dummy_file = os.path.basename(dummy_path)
        scheduler = Scheduler()
        Sequence(
            SshJob(
                node = self.gateway(),
                verbose = True,
                commands = [
                    Run("hostname"),
                    RunScript("tests/script-with-args.sh", "arg1", "arg2"),
                    RunString("for i in $(seq 3); do host fit0$i; done"),
                    Push(localpaths=dummy_path, remotepath="."),
                    Pull(remotepaths=dummy_file, localpath=dummy_path + ".loop"),
                ]),
            SshJob(
                node = LocalNode(),
                critical = True,
                commands = Run("diff {x} {x}.loop".format(x=dummy_path),
                               verbose=True)),
            scheduler = scheduler)
        ok = scheduler.orchestrate()
        ok or scheduler.debrief()
        self.assertTrue(ok)

    def test_x11(self):
        self.run_one_job(
            job = SshJob(
                node = self.gateway(),
                command = [Run("echo $DISPLAY", x11=True),
                           Run("xlsfonts | head -5", x11=True),
                           RunString("""#!/bin/bash
echo tail this time
xlsfonts | tail -5
""", x11=True)]))


    # same but with xterm, so it will hang, so don't call it test_*
    # fit01 must be turned on 
    def xeyes(self):
        node = SshNode(hostname="faraday.inria.fr",
                       username="root",
                       gateway = self.gateway())
        self.run_one_job(
            job = SshJob(
                node = node,
                command = [Run("echo without X11 $DISPLAY"),
                           Run("echo with X11 $DISPLAY", x11=True),
                           Run("xeyes", x11=True)]))

unittest.main()    

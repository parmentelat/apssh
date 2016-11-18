import unittest

import string
import random

from asynciojobs import Engine, Job, Sequence

from apssh import SshNode, SshJob
from apssh import Run, RunScript, RunString, Push, Pull
from apssh import load_agent_keys

from apssh.formatters import ColonFormatter, CaptureFormatter

class Tests(unittest.TestCase):

    def node1(self, capture = False):
        formatter = ColonFormatter() if not capture else CaptureFormatter()
        return SshNode(hostname = 'faraday.inria.fr',
                       username = 'root',
# that's the default anyway
#                       keys=load_agent_keys(),
                       formatter = formatter,
                   )
        
    ########## all the ways to create a simple command

    def run_one_job(self, job):
        engine = Engine(job, verbose=True)
        orchestration = engine.orchestrate()
        engine.list()
        self.assertTrue(orchestration)
        self.assertEqual(job.result(), 0)

    ########## singular command = 
    def test_s1(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 command = [ "echo", "SshJob with s1 command singular", "$(hostname)" ],
                                 label = 's1'
                             ))
        
    def test_s2(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 command = Run("echo", "SshJob with s2 command singular", "$(hostname)"),
                                 label = 's2'
                             ))
        
    def test_s3(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 command = [ Run("echo", "SshJob with s3 command singular", "$(hostname)")] ,
                                 label = 's3'
                             ))
        
    def test_s4(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 command = "echo SshJob with s4 command singular $(hostname)",
                                 label = 's4'
                             ))
    ########## plural commands =
    def test_p1(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 commands = [ "echo", "SshJob with p1 commands plural", "$(hostname)" ],
                                 label = 'p1'
                             ))
        
    def test_p2(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 commands = Run("echo", "SshJob with p2 commands plural", "$(hostname)"),
                                 label = 'p2'
                             ))
        
    def test_p3(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 commands = [ Run("echo", "SshJob with p3 commands plural", "$(hostname)")] ,
                                 label = 'p3'
                             ))
        
    def test_p4(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 commands = "echo SshJob with p4 commands plural $(hostname)",
                                 label = 'p4'
                             ))

    ########## RunScript stuff
    def test_local_script(self):
        self.run_one_job(SshJob(node = self.node1(),
                                command = RunScript("tests/script.sh"),
                                label = 'script'
                            ))
        
    def test_local_script_includes(self):
        self.run_one_job(SshJob(node = self.node1(),
                                command = RunScript("tests/needsinclude.sh",
                                                      includes = [ "tests/inclusion.sh" ]),
                                label = 'script_includes'
                            ))

    def test_local_script_args(self):
        self.run_one_job(SshJob(node = self.node1(),
                                command = RunScript("tests/script-with-args.sh", "foo", "bar", "tutu"),
                                label = 'script'
                            ))
        

    ########## mixing stuff
    def test_mixed_commands(self):
        includes = [ "tests/inclusion.sh" ]
        self.run_one_job(SshJob(node = self.node1(),
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

    def test_string_script(self):
        with open("tests/script-with-args.sh") as reader:
            my_script = reader.read()
        self.run_one_job(SshJob(node = self.node1(),
                                command = RunString(my_script, "foo", "bar", "tutu"),
                                label = "test_string_script"))
    
    def test_string_script_includes(self):
        with open("tests/needsinclude.sh") as reader:
            my_script = reader.read()
        self.run_one_job(SshJob(node = self.node1(),
                                command = RunString(my_script, "some", "'more text'",
                                                       remote_name = "string-script-sample.sh",
                                                       includes = [ "tests/inclusion.sh" ]),
                                label = "test_string_script"))
    
    ########## 
    def test_capture(self):
        node =  self.node1(capture = True)
        self.run_one_job(SshJob(node = node,
                                command = "hostname",
                                label = 'capture'))

        self.assertEqual(node.formatter.get_capture(),"faraday\n")

    def test_logic1(self):
        self.run_one_job(SshJob(node = self.node1(),
                                commands = [ Run("false"),
                                             Run("true") ],
                                label = "should succeed"))
        
    def test_logic2(self):
        todo = SshJob(node = self.node1(),
                      commands = [ Run("true"),
                                   Run("false") ],
                      label = "should fail")
        e = Engine(todo, verbose=True)
        r = e.orchestrate()
        self.assertFalse(r)

    ##########
    def test_file_loopback(self, size=20):
        # randomly create a 2**size chars file
        b1 = "random-{}".format(size)
        b2 = "loopback-{}".format(size)
        b3 = "again-{}".format(size)
        p1 = "tests/" + b1
        p2 = "tests/" + b2
        p3 = "tests/" + b3
        with open(p1, "w") as file1:
            for i in range(2**size):
                file1.write(random.choice(string.ascii_lowercase))

        self.run_one_job(SshJob(node = self.node1(),
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
        self.run_one_job(SshJob(node = self.node1(),
                                commands = [
                                    Run("mkdir -p apssh-tests"),
                                    Pull(remotepaths = "apssh-tests/" + b1, localpath = "tests/" + b3),
                                ]))
        with open(p3) as f3:
            s3 = f3.read()
            self.assertEqual(s1, s3)
                         
            
unittest.main()    

import unittest

from asynciojobs import Engine, Job, Sequence

from apssh import SshNode, SshJob, SshJob, Command, LocalScript, StringScript
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
                                 command = Command("echo", "SshJob with s2 command singular", "$(hostname)"),
                                 label = 's2'
                             ))
        
    def test_s3(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 command = [ Command("echo", "SshJob with s3 command singular", "$(hostname)")] ,
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
                                 commands = Command("echo", "SshJob with p2 commands plural", "$(hostname)"),
                                 label = 'p2'
                             ))
        
    def test_p3(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 commands = [ Command("echo", "SshJob with p3 commands plural", "$(hostname)")] ,
                                 label = 'p3'
                             ))
        
    def test_p4(self):
        self.run_one_job( SshJob(node = self.node1(),
                                 commands = "echo SshJob with p4 commands plural $(hostname)",
                                 label = 'p4'
                             ))

    ########## LocalScript stuff
    def test_local_script(self):
        self.run_one_job(SshJob(node = self.node1(),
                                command = LocalScript("tests/script.sh"),
                                label = 'script'
                            ))
        
    def test_local_script_includes(self):
        self.run_one_job(SshJob(node = self.node1(),
                                command = LocalScript("tests/needsinclude.sh",
                                                      includes = [ "tests/inclusion.sh" ]),
                                label = 'script_includes'
                            ))

    def test_local_script_args(self):
        self.run_one_job(SshJob(node = self.node1(),
                                command = LocalScript("tests/script-with-args.sh", "foo", "bar", "tutu"),
                                label = 'script'
                            ))
        

    ########## mixing stuff
    def test_mixed_commands(self):
        includes = [ "tests/inclusion.sh" ]
        self.run_one_job(SshJob(node = self.node1(),
                                commands = [
                                    LocalScript("tests/needsinclude.sh", "run1", includes = includes),
                                    Command("echo +++++; cat /etc/lsb-release; echo +++++"),
                                    LocalScript("tests/needsinclude.sh", "another", "run", includes = includes)
                                ],
                                label = 'script_commands'
                            ))

    ##########
    def test_string_script(self):
        with open("tests/script-with-args.sh") as reader:
            my_script = reader.read()
        self.run_one_job(SshJob(node = self.node1(),
                                command = StringScript(my_script, "foo", "bar", "tutu"),
                                label = "test_string_script"))
    
    def test_string_script_includes(self):
        with open("tests/needsinclude.sh") as reader:
            my_script = reader.read()
        self.run_one_job(SshJob(node = self.node1(),
                                command = StringScript(my_script,
                                                       remote_name = "string-script-sample.sh",
                                                       includes = [ "tests/inclusion.sh" ]),
                                label = "test_string_script"))
    
    ########## 
    def test_capture(self):
        node =  self.node1(capture = True)
        todo = SshJob(node = node,
                      command = "hostname",
                      label = 'capture')

        self.assertTrue(Engine(todo).orchestrate())
        self.assertEqual(node.formatter.get_capture(),"faraday\n")

    def test_logic1(self):
        todo = SshJob(node = self.node1(),
                      commands = [ Command("false"),
                                   Command("true") ],
                      label = "should succeed")
        self.assertTrue(Engine(todo).orchestrate())
        
#    def test_logic2(self):
#        todo = SshJob(node = self.node1(),
#                      commands = [ Command("true"),
#                                   Command("false") ],
#                      label = "should fail")
#        e = Engine(todo)
#        r = e.orchestrate()
#        print("->", r)
#        e.list()
#        e.why()
#        self.assertFalse(r)

unittest.main()    

import unittest

from asynciojobs import Engine, Job, Sequence

from apssh import SshNode, SshJob, SshJobScript, SshJobCollector, SshJobPusher
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
        

    def test_simple(self):
        todo = SshJob(node=self.node1(),
                      command = [ "echo", "remote hostname=", "$(hostname)" ],
                      label = 'simple'
        )
        self.assertTrue(Engine(todo).orchestrate())

        
    def test_script(self):
        todo = SshJobScript(node=self.node1(),
                            command = [ "tests/testfoo.sh" ],
                            label = 'script'
                        )
        self.assertTrue(Engine(todo).orchestrate())
        
    def test_script_includes(self):
        todo = SshJobScript(node=self.node1(),
                            command = [ "tests/main.sh" ],
                            includes = [ "tests/inclusion.sh" ],
                            label = 'script_includes'
                        )
        self.assertTrue(Engine(todo).orchestrate())

    def test_script_commmands(self):
        todo = SshJobScript(node=self.node1(),
                            commands = [
                                ["tests/main.sh", "run1" ],
                                ["tests/main.sh", "another", "run" ],
                                ],
                            includes = [ "tests/inclusion.sh" ],
                            label = 'script_commands'
                        )
        self.assertTrue(Engine(todo).orchestrate())

    def test_capture(self):
        node =  self.node1(capture = True)
        todo = SshJob(node = node,
                      command = [ "hostname" ],
                      label = 'capture')

        self.assertTrue(Engine(todo).orchestrate())
        self.assertEqual(node.formatter.get_capture(),"faraday\n")

        

unittest.main()    

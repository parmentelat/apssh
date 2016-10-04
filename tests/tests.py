import unittest

from asynciojobs import Engine, Job, Sequence

from apssh import SshNode, SshJob, SshJobScript, SshJobCollector, SshJobPusher
from apssh import load_agent_keys

from apssh.formatters import ColonFormatter

class Tests(unittest.TestCase):

    def node1(self):
        return SshNode(hostname='faraday.inria.fr',
                       username='root',
                       client_keys=load_agent_keys(),
                       formatter=ColonFormatter(),
                   )
        

    def test_simple(self):
        todo = SshJob(node=self.node1(),
                      command = [ "echo", "remote hostname=", "$(hostname)" ],
                      label = 'crap'
        )
        self.assertTrue(Engine(todo).orchestrate())

        
    def test_script(self):
        todo = SshJobScript(node=self.node1(),
                            command = [ "tests/testfoo.sh" ],
                            label = 'crap'
                        )
        self.assertTrue(Engine(todo).orchestrate())
        
    def test_script_includes(self):
        todo = SshJobScript(node=self.node1(),
                            command = [ "tests/main.sh" ],
                            includes = [ "tests/inclusion.sh" ],
                            label = 'crap'
                        )
        self.assertTrue(Engine(todo).orchestrate())

        

unittest.main()    

# iteration 1 : use apssh's sshproxy as-is
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes whose output is text-based 
# but well, right now I'm in a rush and would want to see stuff running...

from apssh.sshproxy import SshProxy
from job import AbstractJob

class SshJob(AbstractJob):

    def __init__(self, proxy, command, label=None, critical=True):
        self.proxy = proxy
        self.command = command
        AbstractJob.__init__(self, forever=False, label=label, critical=critical)

    async def co_run(self):
        return await self.proxy.connect_and_run(self.command, disconnect=False)
        
class SshJobScript(AbstractJob):

    def __init__(self, proxy, local_script, label=None, critical=True):
        self.proxy = proxy
        self.local_script = local_script
        AbstractJob.__init__(self, forever=False, label=label, critical=critical)

    async def co_run(self):
        return await self.proxy.connect_put_and_run(self.local_script, disconnect=False)
        
        

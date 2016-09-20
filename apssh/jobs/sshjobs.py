# iteration 1 : use apssh's sshproxy as-is
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes whose output is text-based 
# but well, right now I'm in a rush and would want to see stuff running...

from apssh.sshproxy import SshProxy

from asynciojobs.job import AbstractJob

# mostly expose a more meaningful name in this context
# probably need a dedicated formatter at some point
class SshNode(SshProxy):
    """
    essentially similar to SshProxy but under a more meaningful name
    """ 
    def __init__(self, *args, **kwds):
        SshProxy.__init__(self, *args, **kwds)

class SshJob(AbstractJob):

    def __init__(self, proxy, command, label=None, critical=True):
        self.proxy = proxy
        self.command = " ".join(command)
        AbstractJob.__init__(self, forever=False, label=label, critical=critical)

    async def co_run(self):
        return await self.proxy.connect_run(self.command, disconnect=False)
        
    async def co_shutdown(self):
        await self.proxy.close()

class SshJobScript(AbstractJob):

    # here the first item in command must be a local filename
    def __init__(self, proxy, command, label=None, critical=True):
        self.proxy = proxy
        self.local_script = command[0]
        self.script_args = command[1:]
        AbstractJob.__init__(self, forever=False, label=label, critical=critical)

    async def co_run(self):
        return await self.proxy.connect_install_run(self.local_script,
                                                    *self.script_args,
                                                    disconnect=False)
        
    async def co_shutdown(self):
        await self.proxy.close()

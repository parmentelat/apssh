# iteration 1 : use apssh's sshproxy as-is
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes whose output is text-based 
# but well, right now I'm in a rush and would want to see stuff running...

from apssh.sshproxy import SshProxy

from asynciojobs.job import AbstractJob

########## SshNode == SshProxy
# it's mostly a matter of exposing a more meaningful name in this context
# might need a dedicated formatter at some point
class SshNode(SshProxy):
    """
    essentially similar to SshProxy but under a more meaningful name
    """ 
    def __init__(self, *args, **kwds):
        SshProxy.__init__(self, *args, **kwds)

class SshJob(AbstractJob):

    def __init__(self, node, command, label=None, critical=True):
        self.node = node
        self.command = " ".join(command)
        AbstractJob.__init__(self, forever=False, label=label, critical=critical)

    async def co_run(self):
        return await self.node.connect_run(self.command, disconnect=False)
        
    async def co_shutdown(self):
        await self.node.close()

class SshJobScript(AbstractJob):

    # here the first item in command must be a local filename
    def __init__(self, node, command, label=None, critical=True):
        self.node = node
        self.local_script = command[0]
        self.script_args = command[1:]
        AbstractJob.__init__(self, forever=False, label=label, critical=critical)

    async def co_run(self):
        return await self.node.connect_put_run(self.local_script,
                                               *self.script_args,
                                               disconnect=False)
        
    async def co_shutdown(self):
        await self.node.close()

class SshJobCollector(AbstractJob):

    def __init__(self, node, remotepaths, localpath, label=None, critical=True):
        self.node = node
        self.remotepaths = remotepaths
        self.localpath = localpath
        AbstractJob.__init__(self, forever=False, label=label, critical=critical)

    async def co_run(self):
        await self.node.get_file_s(self.remotepaths, self.localpath)

    async def co_shutdown(self):
        await self.node.close()    
        
        

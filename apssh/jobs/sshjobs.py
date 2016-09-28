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


########## various kinds of jobs
# XXX it would make sense for sshjob to accept a flag that causes
# it to raise an exception when result is not == 0
# could maybe be the default in fact
class SshJob(AbstractJob):

    """
    Run a command, or list of commands, remotely
    each command is expected as a list of shell tokens that 
    are later assembled using " ".join()
    """

    def __init__(self, node, command=None, commands=None,
                 # set to False if not set explicitly here
                 forever = None,
                 # set to True if not set explicitly here
                 critical = None,
                 *args, **kwds):
        self.node = node
        # commands cab be set with command= or commands= but not both
        if command is None and commands is None:
            print("WARNING: SshJob requires either command or commands")
            self.commands = [ "echo", "misformed", "SshJob"]
        elif command and commands:
            print("WARNING: SshJob created with command and commands - keeping the latter")
            self.commands = commands
        elif command:
            self.commands = [ command ]
        else:
            # allow to pass empty subcommands so one can use if-expressions there
            self.commands = [ x for x in commands if x]
        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

        
    async def co_run(self):
        result = None
        for command in self.commands:
            command_str = " ".join(command)
            result = await self.node.connect_run(command_str, disconnect=False)
            if result != 0:
                raise Exception("command {} returned {} on {}"
                                .format(command_str, result, self.node))
        return result
        
    async def co_shutdown(self):
        await self.node.close()

class SshJobScript(AbstractJob):
    """
    Like SshJob, but the command to run is a local script
    that is pushed remotely first
    For that reason the first item in command must be a local filename
    """
    def __init__(self, node, command,
                 # set to False if not set explicitly here
                 forever = None,
                 # set to True if not set explicitly here
                 critical = None,
                 *args, **kwds):
        self.node = node
        self.local_script = command[0]
        self.script_args = command[1:]
        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

    async def co_run(self):
        result = await self.node.connect_put_run(self.local_script,
                                                 *self.script_args,
                                                 disconnect=False)
        if result != 0:
            raise Exception("command {} {} returned {} on {}"
                            .format(self.local_script, " ".join(self.script_args),
                                    result, self.node))
        
    async def co_shutdown(self):
        await self.node.close()

class SshJobCollector(AbstractJob):
    """
    Retrieve remote files and stores them locally
    """

    def __init__(self, node, remotepaths, localpath,
                 # set to False if not set explicitly here
                 forever = None,
                 # set to True if not set explicitly here
                 critical = None,
                 *args, **kwds):
        self.node = node
        self.remotepaths = remotepaths
        self.localpath = localpath
        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

    async def co_run(self):
        await self.node.get_file_s(self.remotepaths, self.localpath)

    async def co_shutdown(self):
        await self.node.close()    
        
        
class SshJobPusher(AbstractJob):
    """
    Put local files onto target node
    """

    def __init__(self, node, localpaths, remotepath,
                 # set to False if not set explicitly here
                 forever = None,
                 # set to True if not set explicitly here
                 critical = None,
                 *args, **kwds):
        self.node = node
        self.localpaths = localpaths
        self.remotepath = remotepath
        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

    async def co_run(self):
        await self.node.put_file_s(self.localpaths, self.remotepath)

    async def co_shutdown(self):
        await self.node.close()    
        
        

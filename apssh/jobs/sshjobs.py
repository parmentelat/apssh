# iteration 1 : use apssh's sshproxy as-is
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes whose output is text-based 
# but well, right now I'm in a rush and would want to see stuff running...

import os.path

from apssh.sshproxy import SshProxy
from apssh import load_agent_keys

from asynciojobs.job import AbstractJob

########## helper
# let people provide non-str objects when specifying commands
def asemble_command(command):
    if isinstance(command, str):
        return command
    else:
        return " ".join( str(x) for x in command )
        
########## SshNode == SshProxy
# it's mostly a matter of exposing a more meaningful name in this context
# might need a dedicated formatter at some point
class SshNode(SshProxy):
    """
    essentially similar to SshProxy but under a more meaningful name
    """ 
    def __init__(self, *args, keys=None, **kwds):
        keys = keys if keys is not None else load_agent_keys()
        SshProxy.__init__(self, *args, keys=keys, **kwds)


########## various kinds of jobs
# XXX it would make sense for sshjob to accept a flag that causes
# it to raise an exception when result is not == 0
# could maybe be the default in fact
class SshJob(AbstractJob):

    """
    Run a command, or list of commands, remotely
    each command is expected as a list of shell tokens that 
    are later assembled using " ".join()
    
    commands can be set with command= or commands= but not both

    e.g. 
    command = [ "uname", "-a" ]
    or
    commands = [ [ "uname", "-a" ], [ "cat", "/etc/fedora-release" ] ]
    """

    def __init__(self, node, command=None, commands=None,
                 # set to False if not set explicitly here
                 forever = None,
                 # set to True if not set explicitly here
                 critical = None,
                 *args, **kwds):
        self.node = node
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
        # the commands are of course sequential, so we wait for one before we run the next
        for command in self.commands:
            command_str = asemble_command(command)
            result = await self.node.connect_run(command_str, disconnect=False)
            if result != 0:
                raise Exception("command {} returned {} on {}"
                                .format(command_str, result, self.node))
        return result
        
    async def co_shutdown(self):
        await self.node.close()

# xxx : commands instead of command would help
class SshJobScript(AbstractJob):
    """
    Like SshJob, but each command to run is a local script
    that is first pushed remotely
    For that reason the first item in each command must be a local filename
    """
    def __init__(self, node, command=None, commands=None,
                 # set to False if not set explicitly here
                 forever = None,
                 # set to True if not set explicitly here
                 critical = None,
                 # an optional list of local files
                 # to install remotely in the dir where the script is run
                 includes = None,
                 *args, **kwds):
        self.node = node
        if command is None and commands is None:
            print("WARNING: SshJobScript requires either command or commands")
            self.commands = [ "echo", "misformed", "SshJobScript"]
        elif command and commands:
            print("WARNING: SshJobScript created with command and commands - keeping the latter")
            self.commands = commands
        elif command:
            self.commands = [ command ]
        else:
            # allow to pass empty subcommands so one can use if-expressions there
            self.commands = [ x for x in commands if x]

        self.includes = [] if includes is None else includes
        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

    def check_includes(self):
        for include in self.includes:
            if not os.path.exists(include):
                print("WARNING: include not found {}".format(include))

    async def co_run(self):
        result = None
        # run commands sequentially
        # we need to copy the includes only for the first run
        self.check_includes()
        for i, command in enumerate(self.commands):
            local_script = command[0]
            script_args = command[1:]
            # actual copy of includes only for the first command
            includes = self.includes if i == 0 else None
            result = await self.node.connect_put_run(local_script,
                                                     *script_args,
                                                     includes = includes,
                                                     disconnect=False)
            if result != 0:
                raise Exception("command {} {} returned {} on {}"
                                .format(local_script, asemble_command(script_args),
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
                 # asyncssh's SFTP client get option
                 preserve = False, recurse = False, follow_symlinks = False,
                 # this goes to AbstractJob
                 *args, **kwds):
        self.node = node
        self.remotepaths = remotepaths
        self.localpath = localpath
        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        self.preserve = preserve
        self.recurse = recurse
        self.follow_symlinks = follow_symlinks
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

    async def co_run(self):
        await self.node.get_file_s(self.remotepaths, self.localpath,
                                   preserve = self.preserve,
                                   recurse = self.recurse,
                                   follow_symlinks = self.follow_symlinks)

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
                 # asyncssh's SFTP client get option
                 preserve = False, recurse = False, follow_symlinks = False,
                 # this goes to AbstractJob
                 *args, **kwds):
        self.node = node
        self.localpaths = localpaths
        self.remotepath = remotepath
        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        self.preserve = preserve
        self.recurse = recurse
        self.follow_symlinks = follow_symlinks
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

    async def co_run(self):
        await self.node.put_file_s(self.localpaths, self.remotepath,
                                   preserve = self.preserve,
                                   recurse = self.recurse,
                                   follow_symlinks = self.follow_symlinks)                                   

    async def co_shutdown(self):
        await self.node.close()    

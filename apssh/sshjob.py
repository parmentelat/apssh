# use apssh's sshproxy mostly as-is, except for keys handling
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes whose output is text-based 
# but well, right now I'm in a rush and would want to see stuff running...

from asynciojobs.job import AbstractJob

from apssh.sshproxy import SshProxy
from apssh import load_agent_keys

from apssh.commands import AbstractCommand, Run

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

    def user_host(self):
        return "{}@{}".format(self.username, self.hostname)

########## a single kind of job
# that can involve several sorts of commands
# as defined in command.py

class SshJob(AbstractJob):

    """
    A asynciojobs Job object that is set to 
    run a command, or list of commands, remotely
    
    commands can be set as either
    * (1) a list/tuple of AbstractCommands
      e.g.     commands = [ Run(..), RunScript(...), ..]
    * (2) a single instance of AbstractCommand
      e.g.     commands = RunScript(...)
    * (3) a list/tuple of strings -> a single Run object is created
      e.g.     commands = [ "uname", "-a" ]
    * (4) a single string
      e.g.     commands = "uname -a"

    For convenience, you can set commands = or command = 
    (make sure to give exactly one)
    """

    def __init__(self, node, command=None, commands=None,
                 # set to False if not set explicitly here
                 forever = None,
                 # set to True if not set explicitly here
                 critical = None,
                 *args, **kwds):
        self.node = node

        # use command or commands
        if command is None and commands is None:
            print("WARNING: SshJob requires either command or commands")
            commands = [ Run("echo misformed SshJob - no commands nor commands") ]
        elif command and commands:
            print("WARNING: SshJob created with command and commands - keeping the latter")
            commands = commands
        elif command:
            commands = command
        else:
            pass
        
        # find out what really is meant here
        if not commands:
            # cannot tell which case in (1) (2) (3) (4)
            print("WARNING: SshJob requires a meaningful commands")
            self.commands = [ Run("echo misformed SshJob - empty commands") ]
        elif isinstance(commands, str):
            # print("case (4)")
            self.commands = [ Run(commands) ]
        elif isinstance(commands, AbstractCommand):
            # print("case (2)")
            self.commands = [ commands ]
        elif isinstance(commands, (list, tuple)):
            # allows to insert None as a command
            commands = [ c for c in commands if c]
            if not commands:
                commands = [ Run("echo misformed SshJob - need at least one non-void command") ]
            elif isinstance(commands[0], AbstractCommand):
                # print("case (1)")
                # check the list is homogeneous
                if not all( isinstance(c, AbstractCommand) for c in commands):
                    print("WARNING: commands must be a list of AbstractCommand objects")
                self.commands = commands
            else:
                # print("case (3)")
                tokens = commands
                command_args = (str(t) for t in tokens)
                self.commands = [ Run (*command_args) ]
        else:
            print("WARNING: SshJob could not make sense of commands")
            self.commands = [ Run("echo misformed SshJob - could not make sense of commands") ]

        assert(len(self.commands) >= 1)
        assert(all(isinstance(c, AbstractCommand) for c in self.commands))

        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

    async def co_run(self):
        """
        run all commands - i.e. call co_prepare and co_exec
        if the last command does not return 0, then an exception is raised
        so if this job is critical it will abort orchestration 
        """
        result = None
        # the commands are of course sequential, so we wait for one before we run the next
        last_command = self.commands[-1]
        result = None
        for command in self.commands:
            result = await command.co_run(self.node)
            # XXX not clear if we should not ALWAYS raise
            # here, at least if self.critical 
            if command is last_command and result != 0:
                raise Exception("command {} returned {} on {}"
                                .format(command.command(), result, self.node))
        return result
        
    async def co_shutdown(self):
        """
        don't bother to terminate all the commands separately
        all that matters is to terminate the ssh connection to that node
        """
        await self.node.close()


    def details(self):
        return "\n".join(["{}@{}:{}".format(self.node.username, self.node.hostname, c.details())
                          for c in self.commands ])

    def default_label(self):
        first_details = self.commands[0].details()
        first_line = first_details.split("\n")[0]
        return first_line if len(self.commands) == 1 else first_line + " + {} others...".format(len(self.commands)-1)

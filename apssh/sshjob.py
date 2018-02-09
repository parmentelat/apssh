# use apssh's sshproxy mostly as-is, except for keys handling
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes whose output is text-based
# but well, right now I'm in a rush and would want to see stuff running...

from asynciojobs.job import AbstractJob

from .util import check_arg_type
from .sshproxy import SshProxy
from .keys import load_private_keys, load_agent_keys

from .commands import AbstractCommand, Run

from .localnode import LocalNode

########## SshNode == SshProxy
# it's mostly a matter of exposing a more meaningful name in this context
# might need a dedicated formatter at some point


class SshNode(SshProxy):
    """
    essentially similar to SshProxy but under a more meaningful name

    single difference is that private keys are being loaded from the ssh agent 
    if none are passed to the constructor

    """

    def __init__(self, *args, keys=None, **kwds):
        if not keys:
            keys = load_agent_keys()
        if not keys:
            keys = load_private_keys()
        SshProxy.__init__(self, *args, keys=keys, **kwds)

# a single kind of job
# that can involve several sorts of commands
# as defined in command.py


class SshJob(AbstractJob):

    """
    A asynciojobs Job object that is set to 
    run a command, or list of commands, remotely

    As a subclass of `AbstractJob`, this allows you to
    set the `forever` and `critical` flags

    If `verbose` is set to a non-None value, it is used to 
    set - and possibly override - the verbose value in all the
    `commands` in the job

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
    (but make sure to give exactly one of both)
    """

    def __init__(self, node, command=None, commands=None,
                 # set to False if not set explicitly here
                 forever=None,
                 # set to True if not set explicitly here
                 critical=None,
                 # if set, propagate to all commands
                 verbose=None,
                 keep_connection=False,
                 *args, **kwds):
        check_arg_type(node, (SshProxy, LocalNode), "SshJob.node")
        self.node = node
        if not isinstance(node, (SshProxy, LocalNode)):
            print(
                "WARNING: SshJob node field must be an instance of SshProxy (or a subclass like SshNode)")
        self.keep_connection = keep_connection

        # use command or commands
        if command is None and commands is None:
            print("WARNING: SshJob requires either command or commands")
            commands = [
                Run("echo misformed SshJob - no commands nor commands")]
        elif command and commands:
            print(
                "WARNING: SshJob created with command and commands - keeping the latter")
            commands = commands
        elif command:
            commands = command
        else:
            pass

        # find out what really is meant here
        if not commands:
            # cannot tell which case in (1) (2) (3) (4)
            print("WARNING: SshJob requires a meaningful commands")
            self.commands = [Run("echo misformed SshJob - empty commands")]
        elif isinstance(commands, str):
            # print("case (4)")
            self.commands = [Run(commands)]
        elif isinstance(commands, AbstractCommand):
            # print("case (2)")
            self.commands = [commands]
        elif isinstance(commands, (list, tuple)):
            # allows to insert None as a command
            commands = [c for c in commands if c]
            if not commands:
                commands = [
                    Run("echo misformed SshJob - need at least one non-void command")]
            elif isinstance(commands[0], AbstractCommand):
                # print("case (1)")
                # check the list is homogeneous
                if not all(isinstance(c, AbstractCommand) for c in commands):
                    print("WARNING: commands must be a list of AbstractCommand objects")
                self.commands = commands
            else:
                # print("case (3)")
                tokens = commands
                command_args = (str(t) for t in tokens)
                self.commands = [Run(*command_args)]
        else:
            print("WARNING: SshJob could not make sense of commands")
            self.commands = [
                Run("echo misformed SshJob - could not make sense of commands")]

        assert(len(self.commands) >= 1)
        assert(all(isinstance(c, AbstractCommand) for c in self.commands))

        # propagate the verbose flag on all commands if set
        if verbose is not None:
            for command in self.commands:
                command.verbose = verbose
        # set defaults to pass to mother class
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        AbstractJob.__init__(self, forever=forever,
                             critical=critical, *args, **kwds)

    async def co_run(self):
        """
        run all commands - i.e. call co_prepare and co_exec
        if the last command does not return 0, then an exception is raised
        so if this job is critical it will abort orchestration 
        """
        # the commands are of course sequential, so we wait for one before we run the next
        last_command = self.commands[-1]
        overall = 0
        for command in self.commands:
            if isinstance(self.node, LocalNode):
                result = await command.co_run_local(self.node)
            else:
                result = await command.co_run_remote(self.node)
            # one command has failed
            if result != 0:
                if self.critical:
                    # if job is critical, let's raise an exception
                    # so the scheduler will stop
                    raise Exception("command {} returned {} on {}"
                                    .format(command.command(), result, self.node))
                else:
                    # not critical; let's proceed, but let's remember the
                    # overall result is wrong
                    overall = result
        return overall

    async def co_shutdown(self):
        """
        don't bother to terminate all the commands separately
        all that matters is to terminate the ssh connection to that node
        """
        if not self.keep_connection:
            await self.node.close()

    def details(self):
        return "\n".join(["{}@{}:{}".format(self.node.username, self.node.hostname, c.details())
                          for c in self.commands])

    def default_label(self):
        first_details = self.commands[0].details()
        first_line = first_details.split("\n")[0]
        return first_line if len(self.commands) == 1 \
            else first_line + " + {}..".format(len(self.commands) - 1)

    def dot_label(self):
        """
        for producing png example files
        multi-line output, with first nodename,
        and then all the commands
        """
        lines = [self.node.hostname] + [command.details()
                                        for command in self.commands]
        return "\n".join(lines)

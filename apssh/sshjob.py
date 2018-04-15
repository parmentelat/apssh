"""
The SshJob class is a specialization of asynciojobs' Job class
it allows to group operations (commands & file transfers) made in sequence
on a given remote (and even local for convenience) node
"""

from asynciojobs.job import AbstractJob

from .util import check_arg_type
from .sshproxy import SshProxy
from .nodes import LocalNode

from .commands import AbstractCommand, Run


# a single kind of job
# that can involve several sorts of commands
# as defined in command.py


class SshJob(AbstractJob):

    """
    A asynciojobs `Job` object that is set to
    run a command, or list of commands, remotely

    As a subclass of ``AbstractJob``, this allows you to
    set the ``forever`` and ``critical`` flags

    If ``verbose`` is set to a non-None value, it is used to
    set - and possibly override - the verbose value in all the
    `commands` in the job

    ``commands`` can be set as either

    * (1) a list/tuple of ``AbstractCommand`` objects e.g.::

        commands = [ Run(..), RunScript(...), ..]

    * (2) a single instance of ``AbstractCommand``, e.g.::

        commands = RunScript(...)

    * (3) a list/tuple of strings, in which case
      a single ``Run`` object is created, e.g.::

        commands = [ "uname", "-a" ]

    * (4) a single string, here again a single ``Run``
      object is created, e.g.::

        commands = "uname -a"

    For convenience, you can set either ``commands`` or ``command``,
    it is equivalent but make sure to give exactly one of both.
    """

    def __init__(self, node, *args,                     # pylint: disable=r0912
                 command=None, commands=None,
                 # set to False if not set explicitly here
                 forever=None,
                 # set to True if not set explicitly here
                 critical=None,
                 # if set, propagate to all commands
                 verbose=None,
                 keep_connection=False,
                 **kwds):
        check_arg_type(node, (SshProxy, LocalNode), "SshJob.node")
        self.node = node
        self.keep_connection = keep_connection

        # use command or commands
        if command is None and commands is None:
            print("WARNING: SshJob requires either command or commands")
            commands = [
                Run("echo misformed SshJob - no commands nor commands")]
        elif command and commands:
            print(
                "WARNING: SshJob created with command and commands"
                " - keeping the latter only")
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
                    Run("echo misformed SshJob"
                        " - need at least one non-void command")]
            elif isinstance(commands[0], AbstractCommand):
                # print("case (1)")
                # check the list is homogeneous
                if not all(isinstance(c, AbstractCommand) for c in commands):
                    print("WARNING: commands must be"
                          " a list of AbstractCommand objects")
                self.commands = commands
            else:
                # print("case (3)")
                tokens = commands
                command_args = (str(t) for t in tokens)
                self.commands = [Run(*command_args)]
        else:
            print("WARNING: SshJob could not make sense of commands")
            self.commands = [
                Run("echo misformed SshJob"
                    " - could not make sense of commands")]

        assert len(self.commands) >= 1
        assert all(isinstance(c, AbstractCommand) for c in self.commands)

        # propagate the verbose flag on all commands if set
        if verbose is not None:
            for propagate in self.commands:
                propagate.verbose = verbose
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
        # the commands are of course sequential,
        # so we wait for one before we run the next
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
                    raise Exception(
                        "command {} returned {} on {}"
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

    def text_label(self):
        """
        This method customizes rendering of SshJobs for
        calls to a scheduler's ``list()`` or ``debrief()`` methods.

        Relies on the first command's ``label_line()`` method
        """
        first_label = self.commands[0].get_label_line()
        return first_label if len(self.commands) == 1 \
            else first_label + ".. + {}".format(len(self.commands) - 1)

    def graph_label(self):
        """
        This method customizes rendering of SshJobs from
        calls to a scheduler's
        ``graph()`` or ``export_as_dotfile()`` methods.

        Relies on each command's ``label_line()`` method
        """
        return "\n".join(
            ["{}@{}".format(self.node.username,
                            self.node.hostname)]
            + [c.get_label_line() for c in self.commands]
        )

    def details(self):
        """
        Used by SshJob when running list(details=True)
        """
        # tusn out the logic for graph_text is exactly right
        return self.graph_label()

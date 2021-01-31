"""
The ``SshJob`` class is a specialization of ``asynciojobs``' AbstractJob_
class. It allows to group operations (commands & file transfers)
made in sequence on a given remote (and even local for convenience) node.

.. _AbstractJob: http://asynciojobs.readthedocs.io/\
en/latest/API.html#asynciojobs.job.AbstractJob

.. _Scheduler: http://asynciojobs.readthedocs.io/\
en/latest/API.html#module-asynciojobs.scheduler

.. _asynciojobs: http://asynciojobs.readthedocs.io/
"""

from asynciojobs.job import AbstractJob

from .util import check_arg_type
from .sshproxy import SshProxy
from .nodes import LocalNode
from .deferred import Deferred

from .commands import AbstractCommand, Run

class CommandFailedError(Exception):
    """
    The exception class raised when a command that is part
    of a critical SshJob instance fails.

    This is turn is designed to cause the abortion of the
    surrounding scheduler.
    """

    pass


# a single kind of job
# that can involve several sorts of commands
# as defined in command.py


class SshJob(AbstractJob):

    """
    A subclass of asynciojobs_'s AbstractJob_ object that is set to
    run a command, or list of commands, on a remote node specified by a
    :class:`~apssh.nodes.SshNode` object.


    Parameters:
      node: an :class:`SshNode` instance that describes the node
        where the attached commands will run, or the host used
        for file transfers for commands like e.g. :class:`Pull`.
        It is possible to use a :class:`~apssh.nodes.LocalNode` instance too,
        for running commands locally, although some types of commands,
        like precisely file transfers, do not support this.
      command: an alias for ``commands``
      commands: An ordered collection of commands to run sequentially on
        the reference node. for convenience, you can set either
        ``commands`` or ``command``, both forms are equivalent,
        but you need to make sure to give exactly one of both.
        ``commands`` can be set as either in a variety of ways:

          * (1) a list/tuple of ``AbstractCommand`` objects,
            e.g.::

              commands = [ Run(..), RunScript(...), ..]

          * (2) a single instance of ``AbstractCommand``,
            e.g.::

              commands = RunScript(...)

          * (3) a list/tuple of strings, in which case
            a single ``Run`` object is created, e.g.::

              commands = [ "uname", "-a" ]

          * (4) a single string, here again a single ``Run``
            object is created, e.g.::

              commands = "uname -a"

        Regardless, the commands attached internally to a ``SshJob`` objects
        are always represented as a list of :class:`AbstractCommand`
        instances.

      verbose: if set to a non-None value, it is used to
        set - and possibly override - the verbose value in all the
        command instances in the job.
      keep_connection: if set, this flag prevents ``co_shutdown``, when sent
        to this job instance by the scheduler upon completion, from closing
        the connection to the attached node.
      forever: passed to AbstractJob_; default is ``False``, which may differ
        from the one adopted in asynciojobs_.
      critical : passed to AbstractJob_; default is ``True``, which may differ
        from the one adopted in asynciojobs_.
      kwds: passed as-is to AbstractJob_; typically useful for setting
       ``required`` and ``scheduler`` at build-time.
    """

    def __init__(self, node, *,                         # pylint: disable=r0912
                 command=None, commands=None,
                 keep_connection=False,
                 # if set, propagate to all commands
                 verbose=None,
                 # set to False if not set explicitly here
                 forever=None,
                 # set to True if not set explicitly here
                 critical=None,
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
        elif isinstance(commands, (str, Deferred)):
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

        # xxx assign a back-reference from commands to node
        # for the capture mechanism
        for command in self.commands:
          command.node = self.node

        # used in repr_result() to show which command has failed
        self._errors = []
        # propagate the verbose flag on all commands if set
        if verbose is not None:
            for propagate in self.commands:
                propagate.verbose = verbose
        # set defaults to pass to mother class
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        AbstractJob.__init__(self, forever=forever,
                             critical=critical, **kwds)

    async def co_run(self):
        """
        This method is triggered by a running scheduler as part of the
        AbstractJob_ protocol. It simply runs all commands sequentially.

        If any of the commands fail, then the behavious depends on the job's
        ``critical`` flag:

          * if the job is not critical, then all the commands
            are triggered no matter what, and the return code reflects that
            something went wrong by reporting the last failing code;
          * if the job is critical on the other hand, then the first failing
            command causes co_run to stop abruptly and to throw an exception,
            that in turn will cause the surrounding scheduler execution to
            abort immediately.

        Returns:
          int: 0 if everything runs fine, the faulty return code otherwise.

        Raises:
          CommandFailedError: in the case where the object instance is defined
            as ``critical``, and if one of the commands fails, an exception is
            raised, which leads the running scheduler to aborting abruptly.

        """
        # the commands are of course sequential,
        # so we wait for one before we run the next
        overall = 0
        for i, command in enumerate(self.commands, 1):

            # trigger
            if isinstance(self.node, LocalNode):
                result = await command.co_run_local(self.node)
            else:
                result = await command.co_run_remote(self.node)

            # has the command failed ?
            if result == 0 or result in command.allowed_exits:
                pass
            else:
                label = command.get_label_line()
                if self.critical:
                    # if job is critical, let's raise an exception
                    # so the scheduler will stop
                    self._errors.append(f"!Crit![{i}]:{label}->{result}")
                    raise CommandFailedError(
                        f"command {label} returned {result} on node {self.node}")
                else:
                    # not critical; let's proceed, but let's remember the
                    # overall result is wrong
                    self._errors.append(f"Ignr[{i}]:{label}->{result}")
                    overall = result
        return overall

    async def close(self):
        """
        Implemented as part of the AbstractJob_ protocol.

        Default behaviour is to close the underlying ssh connection,
        that is to say the attached `node` object, unless ``keep_connection``
        was set, in which case no action is taken.

        Returns:
          None
        """

        if not self.keep_connection:
            await self.node.close()

    async def co_shutdown(self):
        """
        Implemented as part of the AbstractJob_ protocol.

        Default behaviour is to close the underlying ssh connection,
        that is to say the attached `node` object, unless ``keep_connection``
        was set, in which case no action is taken.

        Returns:
          None
        """
        pass

    def text_label(self):
        """
        This method customizes rendering of this job instance for
        calls to its Scheduler_'s ``list()`` or ``debrief()`` methods.

        Relies on the first command's ``label_line()`` method.
        """
        first_label = self.commands[0].get_label_line()
        return first_label if len(self.commands) == 1 \
            else first_label + f".. + {len(self.commands) - 1}"

    def graph_label(self):
        """
        This method customizes rendering of this job instance for
        calls to its Scheduler_'s
        ``graph()`` or ``export_as_dotfile()`` methods.

        Relies on each command's ``label_line()`` method
        """
        lines = [f"{self.repr_id()}: {self.node.username}@{self.node.hostname}"]
        for command in self.commands:
            line = command.get_label_line()
            if line:
                lines.append(line)
        return "\n".join(lines)

    def details(self):
        """
        Used by Scheduler_ when running ``list(details=True)``
        """
        # turn out the logic for graph_label is exactly right
        return self.graph_label()

    def repr_result(self):                              # pylint: disable=c0111
        if not self.is_running():
            return ""
        if not self._errors:
            return "OK"
        return " - ".join(self._errors)

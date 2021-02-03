"""
The ``commands`` module implements all the command classes, typically
:class:`Run`, :class:`RunScript`, :class:`Pull`, and similar classes.
"""

from pathlib import Path
import random
import re
import copy

from asyncssh import EXTENDED_DATA_STDERR

from .formatters import CaptureFormatter
from .deferred import Capture
from .config import default_remote_workdir

####################
# The base class for items that make a SshJob's commands


class AbstractCommand:

    """
    Abstract base class for all command classes.

    Parameters:
      label: optional label used when representing a scheduler
        textually or graphically
      allowed_exits: the default is to only allow the command to exit(0).
        Using ``allowed_exits``, one can whitelist a set of exit codes
        or signals. If the command returns one of these codes, or receives
        one of these signals, it is deemed to have completed successfully.
        A retcod 0 is always allowed.

    Examples:
      ``allowed_exits=["TERM", 4]`` would allow the command to either
      return exit code ``4``, or to end after receiving signal `'TERM'`.
      Refer to the POSIX documentation for signal names, like `QUIT`
      or `ALRM`.

    Note:
      ``allowed_exits`` is typically useful when a command starts a process
      that is designed to be killed by another command later in the scheduler.
    """

    def __init__(self, *, label=None,
                 allowed_exits=None):
        """
        Some code
        """

        # handle default, create empty set if needed
        if allowed_exits is None:
            allowed_exits = set()
        else:
            allowed_exits = set(allowed_exits)

        # store local attributes
        self.label = label
        self.allowed_exits = allowed_exits

    def __repr__(self):
        return "<{}: {}>".format(type(self).__name__, self.get_label_line())

    ###
    async def co_run_remote(self, node):
        """
        Needs to be redefined on actual command classes.

        Returns:
          Should return 0 if everything is fine.
        """
        pass

    async def co_run_local(self, localnode):

        """
        Needs to be redefined on actual command classes that want
        to support running on a :class:`~apssh.nodes.LocalNode` as well.

        Returns:
          Should return 0 if everything is fine.
        """
        pass

    # extra messages go to stderr and are normally formatted
    def _verbose_message(self, node, message):
        if not hasattr(self, 'verbose') \
                or not self.verbose:                    # pylint: disable=E1101
            return
        if not message.endswith("\n"):
            message += "\n"
        node.formatter.line(message, EXTENDED_DATA_STDERR, node.hostname)

    # descriptive views, required by SshJob
    def get_label_line(self):                           # pylint: disable=c0111
        attempt = self.label
        if attempt is not None:
            return attempt
        attempt = self.label_line()                     # pylint: disable=e1111
        if attempt is not None:
            return attempt
        return "NO-LABEL-LINE (class {})"\
            .format(type(self).__name__)

    def label_line(self):
        """
        Used by SshJob to conveniently show the inside of a Job;
        intended to be redefined by daughter classes.

        Returns:
          str: a one-line string
        """
        pass


class CapturableMixin:
    """
    this class implements the simple logic for capturing a command output

    NOTE. it relies on the presence of the `self.node` attribute that points
    back at the SshNode where this command is going to run;
    which is set by the SshJob class
    """
    def __init__(self, capture: Capture):
        self.capture = capture

    def start_capture(self):
        if self.capture:
            # store the node's formatter and set aside for later
            self.previous_formatter = self.node.formatter
            self.node.formatter = CaptureFormatter()

    def end_capture(self):
        if self.capture:
            # get result from transient formatter
            captured = self.node.formatter.get_capture()
            # restore the node's formatter
            self.node.formatter = self.previous_formatter
            self.previous_formatter = None
            # sanitize
            if captured and captured[-1] == "\n":
                captured = captured[:-1]
            # store captured in self.capture
            variables = self.capture.variables
            varname = self.capture.varname
#            print(f"in variables, {varname} assigned to {captured}")
            variables[varname] = captured


class StrLikeMixin:
    """
    the various Run* classes need to look like a str object for some
    operations, like minimally the following dunder methods

    this is needed for the deferred operation mode, where command objects
    need to remain as Deferred objects and not str, as that would imply early evaluation
    """

    def __str__(self):
        return self._remote_command()

    def __add__(self, strlike):
        result = copy.copy(self)
        result.argv += str(strlike)


class Run(AbstractCommand, CapturableMixin, StrLikeMixin):
    """
    The most basic form of a command is to run a remote command

    Parameters:
      argv: the parts of the remote command.
        The actual command run remotely is obtained by
        concatenating the string representation of each argv
        and separating them with a space.
      label: if set, is used to describe the command in scheduler graphs.
      verbose (bool): if set, the actual command being run is printed out.
      x11 (bool): if set, will enable X11 forwarding, so that a X11 program
        running remotely ends on the local DISPLAY.
      ignore_outputs(bool): this flag is currently used only when running on a LocalNode();
        in that case, the stdout and stderr of the forked process are bound to /dev/null, 
        and no attempt is made to read them; this has turned out a useful trick when
        spawning port-forwarding ssh sessions

    Examples:

      Remotely run ``tail -n 1 /etc/lsb-release`` ::

          Run("tail -n 1 /etc/lsb-release")

      The following forms are exactly equivalent::

          Run("tail", "-n", 1, "/etc/lsb-release")
          Run("tail -n", 1, "/etc/lsb-release")
    """

    # it was tempting to use x11_forwarding as the name here, but
    # first it's definitely too long, given the usage of Run
    # plus, maybe some day we'll need to add other keywords
    # to create_connection than just x11_forwarding,
    # so, it feels about right to call this just like x11
    def __init__(self, *argv,
                 # proper
                 verbose=False, x11=False, ignore_outputs=False,
                 # AbstractCommand
                 label=None, allowed_exits=None,
                 # CapturableMixin
                 capture: Capture = None):
        self.argv = argv
        self.verbose = verbose
        self.x11 = x11
        self.ignore_outputs = ignore_outputs
        AbstractCommand.__init__(self, label=label,
                                 allowed_exits=allowed_exits)
        CapturableMixin.__init__(self, capture)

    def label_line(self):
        """
        One-line rendering is to use the ``label`` attribute if set,
        by default it is the full remote command.
        """
        return self._remote_command()

    def _remote_command(self):
        return " ".join(str(x) for x in self.argv)

    async def co_run_remote(self, node):
        """
        The semantics of running on a remote node.
        """
        self.start_capture()
        command = self._remote_command()
        self._verbose_message(node, "Run: -> {}".format(command))
        # need an ssh connection
        connected = await node.connect_lazy()
        if not connected:
            return
        node_run = await node.run(command, x11_forwarding=self.x11)
        self._verbose_message(
            node, "Run: {} <- {}".format(node_run, command))
        self.end_capture()
        return node_run

    async def co_run_local(self, localnode):
        """
        The semantics of running on a local node.
        """
        self.start_capture()
        command = self._remote_command()
        self._verbose_message(localnode, "Run: -> {}".format(command))
        retcod = await localnode.run(command, ignore_outputs=self.ignore_outputs)
        self._verbose_message(
            localnode, "Run: {} <- {}".format(retcod, command))
        self.end_capture()
        return retcod

# the base class for running a script provided locally
# same as Run, but the command to run remotely is provided
# as a local material, either a local file, or a python string


class RunLocalStuff(AbstractCommand, CapturableMixin, StrLikeMixin):
    """
    The base class for ``RunScript`` and ``RunString``.
    This class implements the common logic for a local script that
    needs to be copied over before being executed.

    Parameters:
      args: the argument list for the remote command
      label: if set, is used to describe the command in scheduler graphs.
      includes: a collection of local files that need to be copied over
        as well; get copied in the same directory as the remote script.
      verbose: print out more information if set; this additionnally causes
        the remote script to be invoked through ``bash -x``, which admittedly
        is totally hacky. xxx we need to remove this.
      remote_basename: an optional name for the remote copy of the script.

    Local commands are copied in a remote directory
    - typically in ``~/.apssh-remote``.

    Also, all copies are done under a name that contains a random string to
    avoid collisions. This is because two parallel runs of the same command
    would otherwise be at risk of one overwriting the remote command file,
    while the second tries to run it, which causes errors like this::

     fit26: .apssh-remote/B3.sh: /bin/bash: bad interpreter: Text file busy

    """

    def __init__(self, args, *,
                 label=None, allowed_exits=None,
                 includes=None, remote_basename=None,
                 x11=False, verbose=False,
                 capture: Capture=None):
        self.args = args
        self.includes = includes if includes is not None else []
        self.remote_basename = remote_basename
        self.x11 = x11
        self.verbose = verbose
        AbstractCommand.__init__(self, label=label,
                                 allowed_exits=allowed_exits)
        CapturableMixin.__init__(self, capture)

    def __str__(self):
        return self._remote_command()

    @staticmethod
    def _random_id():
        """
        Generate a random string to avoid conflicting names
        on the remote host
        """
        return "".join(random.choice('abcdefghijklmnopqrstuvwxyz')
                       for i in range(8))

    def _args_line(self):
        return " ".join(str(x) for x in self.args)

    def _remote_command(self):                          # pylint: disable=c0111
        command = self.remote_basename + " " + self._args_line()
        command = default_remote_workdir + "/" + command
        if self.verbose:
            command = "bash -x " + command
        return command

    async def co_install(self, node, remote_path):
        """
        Abstract method to explain how to remotely install
        a local script before we can invoke it
        """
        print("coroutine method co_install"
              " needs to be redefined on your RunLocalStuff subclass"
              " args are {} and {}".format(node, remote_path))

    async def co_run_remote(self, node):
        """

        Implemented to satisfy the requirement of ``AbstractCommand``.
        The common behaviour for both classes is to first invoke
        :meth:`co_install()` to push the local material
        over; it should raise an exception in case of failure.
        """
        # we need the node to be connected by ssh and SFTP
        # and we need the remote work dir to be created
        if not (await node.sftp_connect_lazy()
                and await node.mkdir(default_remote_workdir)):
            # should never be here
            return

        remote_path = default_remote_workdir + "/" + self.remote_basename

        # do the remote install - depending on the actual class
        await self.co_install(node, remote_path)

        # make sure the remote script is executable - chmod 755
        permissions = 0o755
        await node.sftp_client.chmod(remote_path, permissions)

        if self.includes:
            # sequential is good enough
            for include in self.includes:
                if not Path(include).exists():
                    print("include file {} not found -- skipped"
                          .format(include))
                    continue
                self._verbose_message(
                    node,
                    "RunLocalStuff: pushing include {} in {}"
                    .format(include, default_remote_workdir))
                if not await node.put_file_s(
                        include, default_remote_workdir + "/",
                        follow_symlinks=True):
                    return

        # trigger it
        self.start_capture()
        command = self._remote_command()
        self._verbose_message(node, "RunLocalStuff: -> {}".format(command))
        node_run = await node.run(command, x11_forwarding=self.x11)
        self._verbose_message(
            node, "RunLocalStuff: {} <- {}".format(node_run, command))
        self.end_capture()
        return node_run


# same but using a script that is available as a local file
class RunScript(RunLocalStuff):
    """
    A class to run a **local script file** on the remote system,
    but with arguments passed exactly like with `Run`

    Parameters:
      local_script: the local filename for the script to run remotely
      args: the arguments for the remote script; like with :class:`Run`,
        these are joined with a space character
      label: if set, is used to describe the command in scheduler graphs.
      includes: a collection of local files to be copied over in the same
        location as the remote script, i.e. typically in ``~/.apssh-remote``
      x11 (bool): allows to enable X11 x11_forwarding
      verbose: more output

    Examples:

      Run a local script located in ``../foo.sh`` with specified args::

        RunScript("../foo.sh", "arg1", 2, "arg3")

      or equivalently::

        RunScript("../foo.sh", "arg1 2", "arg3")

    """

    def __init__(self, local_script, *args,
                 label=None, allowed_exits=None,
                 includes=None, x11=False,
                 # if this is set, run bash -x
                 verbose=False,
                 capture: Capture=None):
        self.local_script = local_script
        self.local_basename = Path(local_script).name
        remote_basename = self.local_basename + '-' + self._random_id()

        super().__init__(args,
                         label=label,
                         allowed_exits=allowed_exits,
                         includes=includes,
                         remote_basename=remote_basename,
                         x11=x11, verbose=verbose, capture=capture)

    def label_line(self):
        return "RunScript: " + self.local_basename + " " + self._args_line()

    async def co_install(self, node, remote_path):
        if not Path(self.local_script).exists():
            raise OSError("RunScript : {} not found - bailing out"
                          .format(self.local_script))
        if not await node.put_file_s(
                self.local_script, remote_path,
                follow_symlinks=True):
            return

#####


class RunString(RunLocalStuff):
    """
    Much like RunScript, but the script to run remotely is expected
    to be passed in the first argument as **a python string** this time.

    Parameters:
      script_body(str): the **contents** of the script to run remotely.
      args: the arguments for the remote script; like with :class:`Run`,
        these are joined with a space character
      label: if set, is used to describe the command in scheduler graphs.
      includes: a collection of local files to be copied over in the same
        location as the remote script, i.e. typically in ``~/.apssh-remote``
      x11 (bool): allows to enable X11 x11_forwarding
      remote_name: if provided, will tell how the created script
        should be named on the remote node; it is randomly generated
        if not specified by caller.
      verbose: more output

    Examples:

      Here's how to call a simple bash wrapper remotely::

        myscript = "#!/bin/bash\\nfor arg in "$@"; do echo arg=$arg; done"
        scheduler.add(
          RunString(myscript, "foo", "bar", 2, "arg3",
                    remote_name = "echo-args.sh"))

    """

    def __init__(self, script_body, *args,
                 label=None, allowed_exits=None,
                 includes=None, x11=False,
                 # the name under which the remote command will be installed
                 remote_name=None,
                 # if this is set, run bash -x
                 verbose=False,
                 capture: Capture=None):
        self.script_body = script_body
        if remote_name:
            self.remote_name = remote_name
            # just in case
            remote_basename = Path(self.remote_name).name
            remote_basename += '-' + self._random_id()
        else:
            self.remote_name = ''
            remote_basename = self._random_id()
        super().__init__(args,
                         label=label,
                         allowed_exits=allowed_exits,
                         includes=includes,
                         remote_basename=remote_basename,
                         x11=x11, verbose=verbose,
                         capture=capture)


    @staticmethod
    def _relevant_first_line(body):
        blank = re.compile(r'\A\s*\Z')
        comment = re.compile(r'\A\s*#')
        for line in body.split("\n"):
            if comment.match(line) or blank.match(line):
                continue
            return line.strip()
        return "??? empty body ???"

    WIDTH = 15

    def _truncated(self, width=None):
        if width is None:
            width = self.WIDTH
        body = self._relevant_first_line(self.script_body)
        if len(body) <= width:
            return body
        # generate {:15.15s}...
        truncate_format = "{{:{width}.{width}s}}...".format(width=width)
        return truncate_format.format(body)

    def label_line(self):
        return "RunString: {} {}".format(self._truncated(), self._args_line())


    async def co_install(self, node, remote_path):
        self._verbose_message(
            node, "RunString: pushing script into {}".format(remote_path))
        if not await node.put_string_script(
                self.script_body, remote_path):
            return

####


class Pull(AbstractCommand):
    """
    Retrieve remote files and stores them locally

    Parameters:
      remotepaths: a collection of remote paths to be retrieved.
      localpath: the local directory where to store resulting copies.
      label: if set, is used to describe the command in scheduler graphs.
      verbose (bool): be verbose.
      kwds: passed as-is to the SFTPClient get method.

    See also:
    http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.get

    """

    def __init__(self, remotepaths, localpath,
                 *args,
                 label=None,
                 verbose=False,
                 # asyncssh's SFTP client get options
                 **kwds):
        self.remotepaths = remotepaths
        self.localpath = localpath
        self.verbose = verbose
        self.args = args
        self.kwds = kwds
        super().__init__(label=label)

    def _remote_path(self):
        paths = self.remotepaths
        if isinstance(self.remotepaths, str):
            paths = [paths]
        if len(paths) == 1:
            return paths[0]
        else:
            return "paths[0] ... ({} total)".format(len(paths))

    def label_line(self):
        return "Pull: {} into {}".\
            format(self._remote_path(), self.localpath)

    async def co_run_remote(self, node):
        self._verbose_message(node, "Pull: remotepaths={}, localpath={}"
                              .format(self.remotepaths, self.localpath))
        await node.sftp_connect_lazy()
        await node.get_file_s(self.remotepaths, self.localpath,
                              *self.args, **self.kwds)
        self._verbose_message(node, "Pull done")
        return 0


####
class Push(AbstractCommand):
    """
    Put local files onto target node

    Parameters:
      localpaths: a collection of local filenames to be copied
        over to the remote end.
      remotepath: the directory where to store copied on the remote end.
      label: if set, is used to describe the command in scheduler graphs.
      verbose (bool): be verbose.
      kwds: passed as-is to the SFTPClient put method.

    See also:
    http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.put

    """

    def __init__(self, localpaths, remotepath,
                 *args,
                 label=None,
                 verbose=False,
                 **kwds):
        self.localpaths = localpaths
        self.remotepath = remotepath
        self.verbose = verbose
        self.args = args
        self.kwds = kwds
        super().__init__(label=label)

    def _local_path(self):
        paths = self.localpaths
        if isinstance(self.localpaths, str):
            paths = [paths]
        if len(paths) == 1:
            return paths[0]
        else:
            return "paths[0] ... ({} total)".format(len(paths))

    def label_line(self):
        return "Push: {} onto {}".\
            format(self._local_path(), self.remotepath)

    async def co_run_remote(self, node):
        self._verbose_message(node, "Push: localpaths={}, remotepath={}"
                              .format(self.localpaths, self.remotepath))
        await node.sftp_connect_lazy()
        await node.put_file_s(self.localpaths, self.remotepath,
                              *self.args, **self.kwds)
        self._verbose_message(node, "Push done")
        return 0

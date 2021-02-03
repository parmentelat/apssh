"""
The :class:`SshNode` and :class:`LocalNode` classes are designed
as companions to the :class:`~apssh.sshjob.SshJob` class, that need
a ``node`` attribute to describe on which node to run commands.
"""

import asyncio

import os

from subprocess import PIPE, DEVNULL

from asyncssh import EXTENDED_DATA_STDERR

from .formatters import ColonFormatter

from .sshproxy import SshProxy

from .keys import load_private_keys, load_agent_keys

##########


class LocalNode:
    """
    For convenience and consistency, this class can be used
    as the ``node`` attribute of a :class:`~apssh.sshjob.SshJob` object,
    so as to define a set of commands to run locally.

    Parameters:
      formatter: a formatter instance, default to an instance of
        ``ColonFormatter``;
      verbose: if provided, passed to the formatter instance

    Examples:
      To create a job that runs 2 commands locally::

        SshJob(node=LocalNode(),
               commands = [
                   Run("cat /etc/motd"),
                   Run("sleep 10"),
               ])

    .. note::
      Not all command classes support running on a local node, essentially
        this is only available for usual ``Run`` commands as of this writing.
    """

    def __init__(self, formatter=None, verbose=None):
        self.formatter = formatter or ColonFormatter()
        if verbose is not None:
            self.formatter.verbose = verbose
        # could be improved
        self.hostname = "LOCALNODE"
        # some users reported issues with this so
        # given that it's really only for convenience
        # let's do this best effort
        try:
            self.username = os.getlogin()
        except Exception:                               # pylint: disable=w0703
            self.username = "LOCALUSER"

    # pylint: disable=c0111

    def lines(self, bytes_chunk, datatype):
        # xxx encoding should not be hard-wired
        str_chunk = bytes_chunk.decode("utf-8")
        if str_chunk:
            if str_chunk[-1] == "\n":
                str_chunk = str_chunk[:-1]
            for line in str_chunk.split("\n"):
                self.formatter.line(line + "\n", datatype, self.hostname)

    # from this clue here
    # https://stackoverflow.com/questions/17190221/subprocess-popen\
    # -cloning-stdout-and-stderr-both-to-terminal-and-variables/\
    # 25960956#25960956
    async def read_and_display(self, stream, datatype):
        """
        read (process stdout or stderr) stream line by line
        until EOF and dispatch lines in formatter
        - using self.lines(... datatype)
        """
        while True:
            line = await stream.readline()
            if not line:
                return
            self.lines(line, datatype)

    async def run(self, command, ignore_outputs=False):
        try:
            if not ignore_outputs:
                process = await asyncio.create_subprocess_shell(
                    command, stdout=PIPE, stderr=PIPE)
                # multiplex stdout and stderr on the terminal
                _, _ = await asyncio.gather(
                    self.read_and_display(process.stdout, 0),
                    self.read_and_display(process.stderr, EXTENDED_DATA_STDERR))
                retcod = await process.wait()
                return retcod
            else:
                process = await asyncio.create_subprocess_shell(
                    command, stdout=DEVNULL, stderr=DEVNULL)
                # nothing to read
                self.lines(f"IGNORING (ignore_outputs=True) with `{command}`".encode(),
                           EXTENDED_DATA_STDERR)
                retcod = await process.wait()
                print(f"retcod={retcod}")
                return retcod

        except Exception as exc:                        # pylint: disable=w0703
            line = f"LocalNode: Could not run local command {command} - {exc}"
            self.formatter.line(line, EXTENDED_DATA_STDERR, self.hostname)

    async def close(self):
        pass


# ========== SshNode == SshProxy

# use apssh's sshproxy mostly as-is, except for keys handling
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes
# whose output is text-based but well,
# right now I'm in a rush and would want to see stuff running...

# it's mostly a matter of exposing a more meaningful name in this context
# might need a dedicated formatter at some point


class SshNode(SshProxy):
    """
    An instance of `SshNode` typically is needed to create a
    :class:`apssh.sshjob.SshJob` instance, that defines a batch of commands
    or file transfers to run in sequence on that node.

    Examples:
      A typical usage to create a job that runs 2 commands remotely::

        remote_node = SshNode('remote.foo.com', username='tutu')

        SshJob(node=remote_node,
               commands = [
                   Run("cat /etc/motd"),
                   Run("sleep 10"),
               ])

    This class is a very close specialization of the
    :class:`~apssh.sshproxy.SshProxy` class.
    The only difference are in the handling of default values
    at build time.

    Parameters:
      hostname: remote node's hostname
      username: defaults to ``root`` if unspecified, note that
        :class:`~apssh.sshproxy.SshProxy`'s default is to use
        the local username instead
      keys: filenames for the private keys to use when authenticating;
        the default policy implemented in this class is to first use the
        keys currently loaded in the ssh agent. If none can be found this
        way, `SshNode` will attempt to import the default ssh keys located
        in ``~/.ssh/id_rsa`` and ``~/.ssh/id_dsa``.
      kwds: passed along to the :class:`~apssh.sshproxy.SshProxy` class.

    """

    def __init__(self, hostname, *, username=None, keys=None, **kwds):
        if username is None:
            username = "root"
        if not keys:
            keys = load_agent_keys()
        if not keys:
            keys = load_private_keys()
        SshProxy.__init__(self, hostname, username=username, keys=keys, **kwds)

    def distance(self):
        """
        Returns:
          int: number of hops from the local node.
          An instance without a `gateway` has a distance of 1.
          Otherwise, it is deemed one hop further than its gateway.
        """
        if not self.gateway:                            # pylint: disable=r1705
            return 1
        else:
            return 1 + self.gateway.distance()

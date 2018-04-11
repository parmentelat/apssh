"""
SshNode and LocalNode
"""

import asyncio

import os

from subprocess import PIPE

from asyncssh import EXTENDED_DATA_STDERR

from .formatters import ColonFormatter

from .sshproxy import SshProxy

from .keys import load_private_keys, load_agent_keys

##########


class LocalNode:
    """
    For convenience and consistency, this class essentially
    allows you to describe a set of commands to run locally.

    So you would create a SshJob like always, but would pass
    it an instance of LocalNode() - that is otherwise pretty dumb

    The `formatter` and `verbose` parameters apply like for `SshNode`:
    a `ColonFormatter` is created for you unless you give one, and
    the formatter's `verbose` is set from the LocalNode's `verbose`
    if you give one

    Allows you to create local commands using `Run`

    `RunScript` et `RunString` are not yet implemented,
    but would make sense of course

    `Push` and `Pull` on the other hand are not supported
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

    async def run(self, command):
        try:
            process = await asyncio.create_subprocess_shell(
                command, stdout=PIPE, stderr=PIPE)
            # no need to refer to stdout and stderr
            _, _ = await asyncio.gather(
                self.read_and_display(process.stdout, 0),
                self.read_and_display(process.stderr, EXTENDED_DATA_STDERR))
            retcod = await process.wait()
            return retcod
        except Exception as exc:                        # pylint: disable=w0703
            line = "LocalNode: Could not run local command {} - {}"\
                   .format(command, exc)
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

    Similar to the :py:obj:`apssh.sshproxy.SshProxy`; the differences
    are in the handling of default values at construction time:

    * `username` defaults to "root" if unspecified

    * `keys` when not specified, this class will first try to load your
       ssh agent keys; if no key can be found this way, `SshNode` will
       attempt to import the default ssh keys located in ``~/.ssh/id_rsa``
       and ``~/.ssh/id_dsa``.

    An instance of `SshNode` typically is needed to create a
    :py:obj:`apssh.sshjob.SshJob` instance, that defines a batch of commands
    or file transfers to run in sequence on that node.

    """

    def __init__(self, hostname, *, username=None, keys=None, **kwds):
        if username is None:
            username = "root"
        if not keys:
            keys = load_agent_keys()
        if not keys:
            keys = load_private_keys()
        SshProxy.__init__(self, hostname, username=username, keys=keys, **kwds)

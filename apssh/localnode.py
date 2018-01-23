import asyncio

import os

from subprocess import PIPE

from asyncssh import EXTENDED_DATA_STDERR

from .formatters import ColonFormatter

##########


class LocalNode:
    """
    For convenience and consistency, this class essentially
    allows you to describe a set of commands to run locally.

    So you would create a SshJob like always, but would pass
    it an instance of LocalNode() - that is otherwise pretty dumb

    The `formatter` and `verbose` parameters apply like for `SshNode`:
    a `ColonFormatter` is created for you unless you give one, and
    the formatter's `verbose` is set from the LocalNode's `verbose` if you give one

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
        except:
            self.username = "LOCALUSER"

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
    #-cloning-stdout-and-stderr-both-to-terminal-and-variables/25960956#25960956
    async def read_and_display(self, stream, datatype):
        """
        read (process stdout or stderr) stream line by line
        until EOF and dispatch lines in formatter - using self.lines(... datatype)
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
            stdout, stderr = await asyncio.gather(
                self.read_and_display(process.stdout, 0),
                self.read_and_display(process.stderr, EXTENDED_DATA_STDERR))
            retcod = await process.wait()
            return retcod
        except Exception as e:
            line = "LocalNode: Could not run local command {} - {}"\
                   .format(command, e)
            self.formatter.line(line, EXTENDED_DATA_STDERR, self.hostname)

    async def close(self):
        pass

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

    def __init__(self, formatter = None, verbose = None):
        self.formatter = formatter or ColonFormatter()
        if verbose is not None:
            self.formatter.verbose = verbose
        # xxx could be improved
        self.hostname = "LOCALNODE"
        self.username = os.getlogin()

    def lines(self, bytes_chunk, datatype):
        # xxx encoding should not be hard-wired
        str_chunk = bytes_chunk.decode("utf-8")
        if str_chunk:
            if str_chunk[-1] == "\n":
                str_chunk = str_chunk[:-1]
            for line in str_chunk.split("\n"):
                self.formatter.line(line + "\n", datatype, self.hostname)

    async def run(self, command):
        try:
            process = await asyncio.create_subprocess_shell(
                command, stdout = PIPE, stderr = PIPE)
            # xxx big room for improvement: show stuff on the fly
            # and not in a big batch at the end
            stdout, stderr = await process.communicate()
            # xxx unsure what datatype should be
            # except that it's not EXTENDED_DATA_STDERR
            self.lines(stdout, 0)
            self.lines(stderr, EXTENDED_DATA_STDERR)
            retcod = await process.wait()
            return retcod
        except Exception as e:
            line = "LocalNode: Could not run local command {} - {}"\
                   .format(command, e)
            self.formatter.line(line, EXTENDED_DATA_STDERR, self.hostname)

    async def close(self):
        pass



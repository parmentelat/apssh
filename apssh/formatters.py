import sys
import os, os.path
import asyncio
from asyncssh import EXTENDED_DATA_STDERR

from .util import print_stderr

# asyncio.TimeoutError() has a meaningful repr() but an empty str()
def ensure_visible(exc):
    if isinstance(exc, asyncio.TimeoutError):
        exc = repr(exc)
    return exc

class Formatter:
    """
    This class is an abstract class that allows to define
    how to handle the incoming line of a remote command
    
    This object is expected to be created manually outside of SshProxy logic,
    and then passed to SshProxy

    Examples:
    . RawFormatter:    just ouputs line on stdout
    . ColonFormatter:  outputs hostname + ':' + line - a la grep
    . SubdirFormatter: stores in <subdir>/<hostname> all outputs from that host
    """

    # this seems like a reasonable default
    def connection_failed(self, hostname, username, port, exc):
        exc = ensure_visible(exc)
        print_stderr("{}@{}[{}]:Connection failed:{}".format(username, hostname, port, exc))

    def session_failed(self, hostname, command, exc):
        exc = ensure_visible(exc)
        print_stderr("{} - Session failed {}".format(hostname, exc))

    # events
    def connection_start(self, hostname, direct):
        pass

    def connection_stop(self, hostname):
        pass    

    def session_start(self, hostname, command):
        pass

    def session_stop(self, hostname):
        pass    
    
    # the bulk of the matter
    def line(self, line, datatype, hostname):
        print_stderr("WARNING: class Formatter is intended as a pure abstract class")
        print_stderr("Received line {} from hostname {}".format(line, hostname))
        print_stderr("WARNING: class Formatter is intended as a pure abstract class")

        
class RawFormatter(Formatter):
    """
    Display raw lines as they come
    mostly useless, but useful for development
    """
    def __init__(self, debug=False):
        self.debug = debug
    def connection_start(self, hostname, direct):
        if self.debug:
            msg = "direct" if direct else "tunnelled"
            print_stderr("Connected ({}) to {}".format(msg, hostname))
    def connection_stop(self, hostname):
        if self.debug:
            print_stderr("Disconnected from {}".format(hostname))
    def session_start(self, hostname, command):
        if self.debug:
            print_stderr("Session on {} started for command {}".format(hostname, command))
    def session_stop(self, hostname):
        if self.debug:
            print_stderr("Session ended on {}".format(hostname))
    def line(self, line, datatype, hostname):
        print_function = print_stderr if datatype == EXTENDED_DATA_STDERR else print
        print_function(line, end="")

class ColonFormatter(Formatter):
    """
    Display each line prepended with the hostname and a ':'
    """
    def line(self, line, datatype, hostname):
        print_function = print_stderr if datatype == EXTENDED_DATA_STDERR else print
        print_function("{}:{}".format(hostname, line), end="")

class SubdirFormatter(Formatter):

    def __init__(self, run_name, debug=False):
        self.run_name = run_name
        self._dir_checked = False
        self.debug = debug

    def out(self, hostname):
        return os.path.join(self.run_name, hostname)
    def err(self, hostname):
        return os.path.join(self.run_name, "{}.err".format(hostname))

    def check_dir(self):
        # create directory if needed
        if not self._dir_checked:
            if not os.path.isdir(self.run_name):
                os.makedirs(self.run_name)
            self._dir_checked = True

    def connection_start(self, hostname, direct):
        try:
            self.check_dir()
            # create output file
            with open(self.out(hostname), 'w') as out:
                if self.debug:
                    msg = "direct" if direct else "tunnelled"
                    out.write("Connected ({}) to {}\n".format(msg, hostname))
        except OSError as e:
            print_stderr("File permission problem {}".format(e))
            exit(1)
        except Exception as e:
            print_stderr("Unexpected error {}".format(e))
            exit(1)

    def line(self, line, datatype, hostname):
        filename = self.err(hostname) if datatype == EXTENDED_DATA_STDERR else self.out(hostname)
        with open(filename, 'a') as out:
            out.write(line)

import sys
import time
import os, os.path
import asyncio
from asyncssh import EXTENDED_DATA_STDERR

from .util import print_stderr

# asyncio.TimeoutError() has a meaningful repr() but an empty str()
def ensure_visible(exc):
    if isinstance(exc, asyncio.TimeoutError):
        exc = repr(exc)
    return exc

##############################
class Formatter:
    """
    This class is an abstract class that allows to define
    how to handle the incoming line of a remote command
    plus various events pertaining to an ssh proxy
    
    This object is expected to be created manually outside of SshProxy logic,
    and then passed to SshProxy

    Examples:
    . TermFormatter:   prints out line based on a format (time, hostname, actual line...)
    . RawFormatter:    TermFormatter("%line")
    . ColonFormatter:  TermFormatter("%host:%line")
    . SubdirFormatter: stores in <subdir>/<hostname> all outputs from that host
    """

    def __init__(self, format, verbose=False):
        self.format = format
        self.verbose = verbose

    def _formatted_line(self, line, hostname=None, username=None):
        text = self.format \
                   .replace("%line",line) \
                   .replace("%host", hostname or "") \
                   .replace("%user", "{}@".format(username) if username else "") \
                   .replace("%time", "%H-%M-%S")
        return time.strftime(text)

    # events
    def connection_made(self, hostname, username, direct):
        pass

    def connection_lost(self, hostname, exc, username):
        pass    

    def auth_completed(self, hostname, username):
        pass

    def session_start(self, hostname, command):
        pass

    def session_stop(self, hostname, command):
        pass    
    
    def sftp_start(self, hostname):
        pass
    def sftp_stop(self, hostname):
        pass

    # the bulk of the matter
    def line(self, line, datatype, hostname):
        pass
        
########################################
sep = 10*'='

class TermFormatter(Formatter):
    """
    print raw lines as they come
    (*) regular stdout foes to stdout
    (*) regular stderr, plus event-based annotations like connection open, 
        go on stderr
    """

    def connection_made(self, hostname, username, direct):
        if self.verbose:
            msg = "direct" if direct else "tunnelled"
            line = sep + " Connected ({})".format(msg)
            print_stderr(self._formatted_line(line, hostname, username))
    def connection_lost(self, hostname, exc, username):
        if self.verbose:
            line = sep + " Connection lost {}".format(exc)
            print_stderr(self._formatted_line(line, hostname, username))

    def auth_completed(self, hostname, username):
        if self.verbose:
            line = sep + " Authorization OK with user {}".format(username)
            print_stderr(self._formatted_line(line, hostname, username))

    def session_start(self, hostname, command):
        if self.verbose:
            line = sep + " Session started for {}".format(command)
            print_stderr(self._formatted_line(line, hostname))
    def session_stop(self, hostname, command):
        if self.verbose:
            line = sep + " Session ended for {}".format(command)
            print_stderr(self._formatted_line(line, hostname))

    def sftp_start(self, hostname):
        if self.verbose:
            line = sep + " SFTP subsystem started"
            print_stderr(self._formatted_line(line, hostname))
    def sftp_stop(self, hostname):
        if self.verbose:
            line = sep + " SFTP subsystem stopped"
            print_stderr(self._formatted_line(line, hostname))

    def line(self, line, datatype, hostname):
        print_function = print_stderr if datatype == EXTENDED_DATA_STDERR else print
        print_function(self._formatted_line(line, hostname), end="")

class RawFormatter(TermFormatter):
    """
    TermFormatter(format="%line")
    """
    def __init__(self, *args, **kwds):
        Formatter.__init__(self, "%line", *args, **kwds)
        
class ColonFormatter(TermFormatter):
    """
    TermFormatter(format="%host:%line")
    """
    def __init__(self, *args, **kwds):
        Formatter.__init__(self, "%user%host:%line", *args, **kwds)
        
class TimeColonFormatter(TermFormatter):
    """
    TermFormatter(format="%H-%M-%S:%host:%line")
    """
    def __init__(self, *args, **kwds):
        Formatter.__init__(self, "%time:%host:%line", *args, **kwds)
        
########################################
class SubdirFormatter(Formatter):

    def __init__(self, run_name, verbose=False):
        self.run_name = run_name
        self._dir_checked = False
        Formatter.__init__(self, "%line", verbose = verbose)

    def out(self, hostname):
        return os.path.join(self.run_name, hostname)
    def err(self, hostname):
        return os.path.join(self.run_name, "{}.err".format(hostname))

    def filename(self, hostname, datatype):
        return self.err(hostname) if datatype == EXTENDED_DATA_STDERR else self.out(hostname)

    def check_dir(self):
        # create directory if needed
        if not self._dir_checked:
            if not os.path.isdir(self.run_name):
                os.makedirs(self.run_name)
            self._dir_checked = True

    def connection_made(self, hostname, username, direct):
        try:
            self.check_dir()
            # create output file
            with open(self.out(hostname), 'w') as out:
                if self.verbose:
                    msg = "direct" if direct else "tunnelled"
                    out.write("Connected ({}) to {}@{}\n".format(msg, username, hostname))
        except OSError as e:
            print_stderr("File permission problem {}".format(e))
            exit(1)
        except Exception as e:
            print_stderr("Unexpected error {}".format(e))
            exit(1)

    def line(self, line, datatype, hostname):
        filename = self.filename(hostname, datatype)
        with open(filename, 'a') as out:
            out.write(self._formatted_line(line, hostname))

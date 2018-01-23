import sys
import time
import os
from pathlib import Path
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

    * VerboseFormatter:  prints out ssh-details based on verbose flag

    * TerminalFormatter: prints out line based on a format (time, hostname, actual line...)

    * RawFormatter:      TerminalFormatter("@line@")

    * ColonFormatter:    TerminalFormatter("@host@:@line@")

    * SubdirFormatter:   stores in <subdir>/<hostname> all outputs from that host
    """

    time_format = "%H-%M-%S"

    def __init__(self, format):
        self.format = format.replace("@time@", self.time_format)

    def _formatted_line(self, line, hostname=None, username=None):
        return time.strftime(self.format) \
                   .replace("@line@", line) \
                   .replace("@host@", hostname or "") \
                   .replace("@user@", "{}@".format(username) if username else "")

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
sep = 10 * '='


class VerboseFormatter(Formatter):
    """
    plus event-based annotations like connection open, go on stderr
    if verbose is specified
    """

    def __init__(self, format, verbose):
        self.verbose = verbose
        Formatter.__init__(self, format)

    def connection_made(self, hostname, username, direct):
        if self.verbose:
            msg = "direct" if direct else "tunnelled"
            line = sep + " Connecting ({}) to {}@{}"\
                .format(msg, username, hostname)
            print_stderr(self._formatted_line(line, hostname, username))

    def connection_lost(self, hostname, exc, username):
        # exception being not None means something went wrong
        # so always notify in this case
        if exc:
            adjective = "failed"
            print_stderr("Connection failed to {}@{} : {}"
                         .format(username, hostname, exc.reason))
#            print("code =", exc.code, "reason=", exc.reason)
        else:
            adjective = "closed"
        if self.verbose:
            line = sep + " Connection {} to {}@{}"\
                .format(adjective, username, hostname)
            print_stderr(self._formatted_line(line, hostname, username))

    def auth_completed(self, hostname, username):
        if self.verbose:
            line = sep + " Authorization OK {}@{}"\
                .format(username, hostname)
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


class TerminalFormatter(VerboseFormatter):
    """
    print raw lines as they come

    * regular stdout goes to stdout

    * regular stderr, plus event-based annotations like connection open, go on stderr
    """

    def line(self, line, datatype, hostname):
        print_function = print_stderr if datatype == EXTENDED_DATA_STDERR else print
        print_function(self._formatted_line(line, hostname), end="")


class RawFormatter(TerminalFormatter):
    """
    TerminalFormatter(format="@line@")
    """

    def __init__(self, format, verbose=True):
        TerminalFormatter.__init__(self, "@line@", verbose)


class ColonFormatter(TerminalFormatter):
    """
    TerminalFormatter(format="@host@:@line@")
    """

    def __init__(self, verbose=True):
        TerminalFormatter.__init__(self, "@user@@host@:@line@", verbose)


class TimeColonFormatter(TerminalFormatter):
    """
    TerminalFormatter(format="%H-%M-%S:@host@:@line@")
    """

    def __init__(self, verbose=True):
        TerminalFormatter.__init__(self, "@time@:@host@:@line@", verbose)

########################################


class SubdirFormatter(VerboseFormatter):
    """
    Stores outputs in a subdirectory run_name, 
    in a file named after the hostname
    """

    def __init__(self, run_name, verbose=True):
        self.verbose = verbose
        self.run_name = run_name
        Formatter.__init__(self, "@line@")
        self._dir_checked = False

    def out(self, hostname):
        return str(Path(self.run_name) / hostname)

    def err(self, hostname):
        return str(Path(self.run_name) / "{}.err".format(hostname))

    def filename(self, hostname, datatype):
        return self.err(hostname) if datatype == EXTENDED_DATA_STDERR else self.out(hostname)

    def check_dir(self):
        # create directory if needed
        if not self._dir_checked:
            if not Path(self.run_name).is_dir():
                os.makedirs(self.run_name)
            self._dir_checked = True

    def connection_made(self, hostname, username, direct):
        try:
            self.check_dir()
            # create output file
            with open(self.out(hostname), 'w') as out:
                if self.verbose:
                    msg = "direct" if direct else "tunnelled"
                    out.write("Connected ({}) to {}@{}\n".format(
                        msg, username, hostname))
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

########################################


class CaptureFormatter(VerboseFormatter):
    """
    This class allows to implement something like this bash fragment
    x=$(ssh hostname command)
    For now it just provides options to start and get capture
    """

    def __init__(self, format="@line@", verbose=True):
        VerboseFormatter.__init__(self, format, verbose)
        self.start_capture()

    def start_capture(self):
        """
        as the name suggests, mark the current capture as void
        """
        self._capture = ""

    def get_capture(self):
        """
        return the lines captured since last `start_capture()`
        """
        return self._capture

    def line(self, line, datatype, hostname):
        if datatype != EXTENDED_DATA_STDERR:
            self._capture += line
        else:
            print_stderr(self._formatted_line(line, hostname), end="")

"""
A formatter is a class that knows how to deal with the
stdout/stderr lines as they come back from a ssh connection.


In its capture form, it allows to retain this output
in memory instead of printing on the fly.
"""

import time
import os
from pathlib import Path
import asyncio
from asyncssh import EXTENDED_DATA_STDERR

from .util import print_stderr

# asyncio.TimeoutError() has a meaningful repr() but an empty str()


def ensure_visible(exc):                                # pylint: disable=c0111
    if isinstance(exc, asyncio.TimeoutError):
        exc = repr(exc)
    return exc

##############################


class Formatter:
    """
    This class is an abstract class that allows to describe
    how to handle the incoming text from a remote command,
    as well as various events pertaining to an
    :class:`~apssh.sshproxy.SshProxy`.

    This object is expected to be created manually outside of the
    :class:`~apssh.sshproxy.SshProxy` logic.

    Examples of predefined formatters:

    * ``TerminalFormatter``: prints out line based on a format
      (time, hostname, actual line...).

    * ``RawFormatter``:    shortcut for ``TerminalFormatter("@line@")``.

    * ``ColonFormatter``:  shortcut for ``TerminalFormatter("@host@:@line@")``.

    * ``SubdirFormatter``: stores in ``<subdir>/<hostname>``
      all outputs from that host.

    * ``CaptureFormatter``: stores flow in-memory
      instead of printing on the fly.
    """

    time_format = "%H-%M-%S"

    def __init__(self, custom_format):
        self.format = custom_format.replace("@time@", self.time_format)

    def _formatted_line(self, line, hostname=None, username=None):
        return (time.strftime(self.format)
                   .replace("@line@", line)
                   .replace("@host@", hostname or "")
                   .replace("@user@", f"{username}@" if username else ""))

    # pylint: disable=c0111

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

    def stderr_line(self, line, hostname):
        return self.line(line + "\n", EXTENDED_DATA_STDERR, hostname)

########################################
SEP = 10 * '='


class VerboseFormatter(Formatter):
    """
    plus event-based annotations like connection open, go on stderr
    if verbose is specified
    """

    def __init__(self, custom_format, verbose):
        self.verbose = verbose
        Formatter.__init__(self, custom_format)

    def connection_made(self, hostname, username, direct):
        if self.verbose:
            msg = "direct" if direct else "tunnelled"
            line = SEP + f" Connecting ({msg}) to {username}@{hostname}"
            print_stderr(self._formatted_line(line, hostname, username))

    def connection_lost(self, hostname, exc, username):
        # exception being not None means something went wrong
        # so always notify in this case
        if exc:
            adjective = "failed"
            # not all exceptions have a reason attribute
            displayed = getattr(exc, 'reason', exc)
            print_stderr(f"Connection failed to {username}@{hostname} : {displayed}")
        else:
            adjective = "closed"
        if self.verbose:
            line = SEP + f" Connection {adjective} to {username}@{hostname}"
            print_stderr(self._formatted_line(line, hostname, username))

    def auth_completed(self, hostname, username):
        if self.verbose:
            line = SEP + f" Authorization OK {username}@{hostname}"
            print_stderr(self._formatted_line(line, hostname, username))

    def session_start(self, hostname, command):
        if self.verbose:
            line = SEP + f" Session started for {command}"
            print_stderr(self._formatted_line(line, hostname))

    def session_stop(self, hostname, command):
        if self.verbose:
            line = SEP + f" Session ended for {command}"
            print_stderr(self._formatted_line(line, hostname))

    def sftp_start(self, hostname):
        if self.verbose:
            line = SEP + " SFTP subsystem started"
            print_stderr(self._formatted_line(line, hostname))

    def sftp_stop(self, hostname):
        if self.verbose:
            line = SEP + " SFTP subsystem stopped"
            print_stderr(self._formatted_line(line, hostname))


class TerminalFormatter(VerboseFormatter):
    """
    Use ``print()`` to render raw lines as they come.
    Remote stdout goes to stdout of course. Remote stderr goes to stderr.
    If the ``verbose`` attribute is set, additional ssh-related
    events, like connection open and similar, are also issued on stderr.

    Parameters:
      custom_format: a string that describes the format used to print out
        incoming lines, see below.
      verbose: when set, additional information get issued as well,
        typically pertaining to the establishment of the ssh connection.

    The ``custom_format`` attribute can contain the following keywords,
    that are expanded when actual traffic occurs.

    * ``@line@`` the raw contents as sent over the wire
    * ``@host@@`` the remote hostname
    * ``@user@`` the remote username
    * ``%H`` and similar time-oriented formats, applied to the time
      of local reception; refer to strftime_ for
      a list of supported formats.
    * ``@time@`` is a shortcut for ``"%H-%M-%S"``.

    .. _strftime: https://docs.python.org/\
3/library/datetime.html#strftime-and-strptime-behavior
    """

    def line(self, line, datatype, hostname):
        print_function = \
            print_stderr if datatype == EXTENDED_DATA_STDERR else print
        print_function(self._formatted_line(line, hostname), end="")


class RawFormatter(TerminalFormatter):
    """
    TerminalFormatter(format="@line@")
    """

    def __init__(self, *, verbose=True):
        TerminalFormatter.__init__(self, "@line@", verbose)


class ColonFormatter(TerminalFormatter):
    """
    TerminalFormatter(format="@host@:@line@")
    """

    def __init__(self, *, verbose=True):
        TerminalFormatter.__init__(self, "@user@@host@:@line@", verbose)


class TimeColonFormatter(TerminalFormatter):
    """
    TerminalFormatter(format="%H-%M-%S:@host@:@line@")
    """

    def __init__(self, *, verbose=True):
        TerminalFormatter.__init__(self, "@time@:@host@:@line@", verbose)

########################################


class SubdirFormatter(VerboseFormatter):
    """
    This class allows to store remote outputs on the filesystem rather
    than on the terminal, using the remote hostname as the base for
    the local filename.

    With this class, the remote stdout, stderr, as well as ssh events
    if requested, are all merged in a single output file,
    named after the hostname.

    Parameters:
      run_name: the name of a local directory where to store the resulting
        output; this directory is created if needed.
      verbose: allows to see ssh events in the resulting file.

    Examples:
      If ``run_name`` is set to ``probing``, the session for
      host ``foo.com`` will end up in file ``probing/foo.com``.
    """

    def __init__(self, run_name, *, verbose=True):
        self.run_name = run_name
        VerboseFormatter.__init__(self, "@line@", verbose)
        self._dir_checked = False

    # pylint: disable=c0111
    def out(self, hostname):
        return str(Path(self.run_name) / hostname)

    def err(self, hostname):
        return str(Path(self.run_name) / f"{hostname}.err")

    def filename(self, hostname, datatype):
        return self.err(hostname) if datatype == EXTENDED_DATA_STDERR \
            else self.out(hostname)

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
                    out.write(f"Connected ({msg}) to {username}@{hostname}\n")
        except OSError as exc:
            print_stderr(f"File permission problem {exc}")
            exit(1)
        except Exception as exc:                        # pylint: disable=W0703
            print_stderr(f"Unexpected error {type(exc)} {exc}")
            exit(1)

    def line(self, line, datatype, hostname):
        filename = self.filename(hostname, datatype)
        with open(filename, 'a') as out:
            out.write(self._formatted_line(line, hostname))

########################################


class CaptureFormatter(VerboseFormatter):
    """
    This class allows to capture remote output in memory.
    For now it just provides options to start and get a capture.

    Examples:

      To do a rough equivalent of bash's::

        captured_output=$(ssh remote.foo.com cat /etc/release-notes)

      You would do this::

        s = Scheduler()
        f = CaptureFormatter()
        n = SshNode('remote.foo.com', formatter=f)
        s.add(SshJob(node=n, command="cat /etc/release-notes"))

        f.start_capture()
        s.run()
        captured = f.get_capture()

    """

    def __init__(self, custom_format="@line@", verbose=True):
        VerboseFormatter.__init__(self, custom_format, verbose)
        self.start_capture()

    def start_capture(self):
        """
        Marks the current capture as void.
        """
        self._capture = ""

    def get_capture(self):
        """
        Returns:
            str: the lines captured since last ``start_capture()``
        """
        return self._capture

    def line(self, line, datatype, hostname):
        if datatype != EXTENDED_DATA_STDERR:
            self._capture += line
        else:
            print_stderr(self._formatted_line(line, hostname), end="")

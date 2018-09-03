#!/usr/bin/env python3

"""
The SshProxy class models an ssh connection, and is mainly in charge
* lazily initializing connections on a need-by-need basis
* and reasembling lines as they come back from the remote
"""

import asyncio

import asyncssh

from .util import print_stderr, check_arg_type
# a dummy formatter
from .formatters import ColonFormatter


class _LineBasedSession(asyncssh.SSHClientSession):
    """
    A session that records both outputs (out and err)
    in its internal attributes.
    It also may have an associated formatter (through its proxy reference)
    and in that case the formatter receives a line() call
    each time a line is received.
    """

    ##########
    class Channel:
        """
        typically a session will have one Channel for stdout and one for stderr

        aggregates text as it comes in
        .buffer: gathers the full contents
        .line: the current line
        """

        def __init__(self, name, proxy):
            self.name = name
            self.proxy = proxy
            # buffering
            self.buffer = ""
            self.line = ""

        # pylint: disable=c0111
        def data_received(self, data, datatype):
            # preserve it before any postprocessing occurs
            self.buffer += data
            # not adding a \n since it's already in there
            if self.proxy.debug:
                print_stderr('BS {} DR: -> {} [[of type {}]]'.
                             format(self.proxy.hostname, data, self.name))
            chunks = [x for x in data.split("\n")]
            # len(chunks) cannot be 0
            assert chunks != [], "unexpected data received"
            # what goes in the current line, if any
            current_line = chunks.pop(0)
            self.line += current_line
            for chunk in chunks:
                # restore the \n that we removed by calling split
                self.flush(datatype, newline=True)
                self.line = chunk

        def flush(self, datatype, newline):
            # add newline to current line f requested
            if newline:
                self.line += "\n"
            # actually write line, if there's anything to write
            # (EOF calls flush too)
            if self.line:
                self.proxy.formatter.line(self.line, datatype,
                                          self.proxy.hostname)
                self.line = ""

    ##########
    def __init__(self, proxy, command, *args, **kwds):
        # self.proxy is expected to be set already by the closure/subclass
        self.proxy = proxy
        self.command = command
        self.stdout = self.Channel("stdout", proxy)
        self.stderr = self.Channel("stderr", proxy)
        self._exit = None
        super().__init__(*args, **kwds)

    # this seems right only for text streams...
    def data_received(self, data, datatype):
        channel = self.stderr if datatype == asyncssh.EXTENDED_DATA_STDERR \
            else self.stdout
        channel.data_received(data, datatype)

    def connection_made(self, conn):               # pylint:disable=w0221,w0613
        self.proxy.formatter.session_start(self.proxy.hostname, self.command)

    def connection_lost(self, exc):
        self.proxy.formatter.session_stop(self.proxy.hostname, self.command)

    def eof_received(self):
        self.stdout.flush(None, newline=False)
        self.stderr.flush(asyncssh.EXTENDED_DATA_STDERR, newline=False)
        self.proxy.debug_line("EOF")

    def exit_status_received(self, status):
        self._exit = status
        self.proxy.debug_line("STATUS = {}\n".format(status))

    def exit_signal_received(self, signal,
                             core_dumped, msg, lang):   # pylint: disable=w0613
        # When a process now receive a signal that make him exit,
        # we will put the name of the signal as _exit so
        # that we avoid error type "task [...] returned None on node ...."
        self._exit = signal
        self.proxy.debug_line("SIGNAL = {}--{}\n".format(signal, msg))

# _VerboseClient is created through factories attached to each proxy

class _VerboseClient(asyncssh.SSHClient):

    # pylint: disable=c0111

    def __init__(self, proxy, direct, *args, **kwds):
        self.proxy = proxy
        self.formatter = proxy.formatter
        self.direct = direct
        self._connection_lost = False
        asyncssh.SSHClient.__init__(self, *args, **kwds)

    def connection_made(self, conn):
        self.formatter.connection_made(
            self.proxy.hostname, self.proxy.username, self.direct)

    # xxx we don't get this; at least, not always
    # the issue seems to be that we use close() on the asyncssh connection
    # which is a synchroneous call and I am not sure
    # for what other future I should await instead/afterwards
    # this actually triggers though occasionnally esp. with several targets
    def connection_lost(self, exc):
        self.formatter.connection_lost(
            self.proxy.hostname, exc, self.proxy.username)
        if exc:
            self._connection_lost = True

    def auth_completed(self):
        self.formatter.auth_completed(self.proxy.hostname, self.proxy.username)

####################


class SshProxy:                                         # pylint: disable=r0902
    """
    A proxy essentially wraps an ssh connection.
    It can connect to a remote, and then can run several
    commands in the most general sense, i.e. including file transfers.

    Parameters:
      hostname: remote hostname
      username: remote login name
      gateway (SshProxy):  when set, this node is then used as a hop
        for creating a 2-leg ssh connection.

      formatter: each SshProxy instance has an attached formatter that
        is in charge of rendering the output of the various commands.
        The default is to use an instance of
        :class:`~apssh.formatters.ColonFormatter`, that
        outputs lines of the form ``hostname:actual-output``

      verbose: allows to get some user-level feedback on ssh
        negociation. `Permission denied` messages and similar won't show up
        unless verbose is set.

    """

    def __init__(self, hostname, *, username=None,
                 gateway=None,  # if another SshProxy is given
                                # it is used as an ssh gateway
                 keys=None,     # this class has no smart way to guess for keys
                 known_hosts=None, port=22,
                 formatter=None, verbose=None,
                 debug=False, timeout=30):
        # early type verifications
        check_arg_type(hostname, str, "SshProxy.hostname")
        self.hostname = hostname
        check_arg_type(username, (str, type(None)), "SshProxy.username")
        self.username = username
        self.known_hosts = known_hosts
        self.keys = keys if keys is not None else []
        self.port = int(port)
        check_arg_type(gateway, (SshProxy, type(None)), "SshProxy.gateway")
        self.gateway = gateway
        # if not specified we use a basic colon formatter
        self.formatter = formatter or ColonFormatter()
        if verbose is not None:
            self.formatter.verbose = verbose
        self.debug = debug
        self.timeout = timeout
        #
        self.conn, self.sftp_client = None, None
        self.client = None
        # critical sections require mutual exclusions
        self._connect_lock = asyncio.Lock()
        self._disconnect_lock = asyncio.Lock()

    # make this an asynchroneous context manager
    # async with SshProxy(...) as ssh:
    #
    async def __aenter__(self):
        await self.connect_lazy()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        # xxx this might be a little harsh, in the case
        # where an exception did occur
        await self.close()

    def __user_host__(self):
        return "{}@{}".format(self.username, self.hostname) if self.username \
            else "@" + self.hostname

    def __repr__(self):
        text = "" if not self.gateway \
               else "{} <--> ".format(self.gateway.__user_host__())
        text += self.__user_host__() + " "
        text += "[no key] " if not self.keys else "[{} keys] ".format(
            len(self.keys))
        if self.conn:
            text += "<-SSH->"
        if self.sftp_client:
            text += "<-SFTP->"
        return "<{} {}>".format(type(self).__name__, text)

    def debug_line(self, line):                         # pylint: disable=c0111
        if line.endswith("\n"):
            line = line[:-1]
        line += " ((from:" + repr(self) + "))\n"
        if self.debug:
            self.formatter.line(
                line, asyncssh.EXTENDED_DATA_STDERR, self.hostname)

    def is_connected(self):
        """
        Returns:
           bool: whether the connection is up
        """
        return self.conn is not None

    async def connect_lazy(self):
        """
        Connects if needed - uses a lock to make it safe for several coroutines
        to simultaneously try to run commands on the same SshProxy instance.

        Returns:
          connection object
        """
        async with self._connect_lock:
            if self.conn is None:
                await self._connect()
        return self.conn

    async def _connect(self):
        """
        Unconditionnaly attemps to connect and raise an exception otherwise
        """
        if self.gateway:
            return await self._connect_tunnel()
        return await self._connect_direct()

    async def _connect_direct(self):
        """
        The code for connecting to the first ssh hop
        (i.e. when self.gateway is None)
        """
        assert self.gateway is None

        # pylint: disable=c0111
        class ClientClosure(_VerboseClient):
            # it is crucial that the first param here is *NOT* called self
            def __init__(client_self, *args, **kwds):   # pylint: disable=e0213
                _VerboseClient.__init__(
                    client_self, self, direct=True, *args, **kwds)

        self.debug_line("SSH direct connecting")
        # second returned value is client, but is unused
        self.conn, self.client = \
            await asyncio.wait_for(
                asyncssh.create_connection(
                    ClientClosure, self.hostname, port=self.port,
                    username=self.username,
                    known_hosts=self.known_hosts, client_keys=self.keys
                ),
                timeout=self.timeout)

    async def _connect_tunnel(self):
        """
        The code to connect to a higher-degree hop
        We expect gateway to have its connection open,
        and issue connect_ssh on that connection
        """
        # make sure the gateway has connected already
        assert self.gateway is not None
        await self.gateway.connect_lazy()

        # pylint: disable=c0111
        class ClientClosure(_VerboseClient):
            def __init__(client_self, *args, **kwds):   # pylint: disable=e0213
                _VerboseClient.__init__(
                    client_self, self, direct=False, *args, **kwds)

        self.debug_line("SSH tunnel connecting")
        # second returned value is client, but is unused
        try:
            self.conn, self.client = \
                await asyncio.wait_for(
                    self.gateway.conn.create_ssh_connection(
                        ClientClosure, self.hostname, port=self.port,
                        username=self.username,
                        known_hosts=self.known_hosts, client_keys=self.keys
                    ),
                    timeout=self.timeout)
            self.debug_line("SSH tunnel connected")
        except asyncssh.misc.ChannelOpenError:
            self.formatter.stderr_line(
                "Cannot open channel to {}@{}"
                .format(self.username, self.hostname),
                self.hostname)
            raise

    def is_sftp_connected(self):
        """
        Returns:
          bool: whether the SFTP subsystem is up
        """
        return self.sftp_client is not None

    async def sftp_connect_lazy(self):
        """
        Initializes SFTP connection if needed

        Returns:
          SFTP connection object
        """

        await self.connect_lazy()
        async with self._connect_lock:
            if self.sftp_client is None:
                await self._sftp_connect()
        return self.sftp_client

    async def _sftp_connect(self):
        if self.conn is None:
            return False
        try:
            self.sftp_client = await self.conn.start_sftp_client()
            self.formatter.sftp_start(self.hostname)
        except asyncssh.sftp.SFTPError:
            self.formatter.stderr_line(
                "Cannot start STFP subsystem".format(),
                self.hostname,
            )
            raise

    async def _close_sftp(self):
        """
        close the SFTP client if relevant
        """
        if self.sftp_client is not None:
            # set self.sftp_client to None *before* awaiting
            # to avoid duplicate attempts
            preserve = self.sftp_client
            self.sftp_client = None
            try:
                preserve.exit()
            except Exception:                           # pylint: disable=w0703
                pass
            await preserve.wait_closed()
            self.formatter.sftp_stop(self.hostname)

    async def _close_ssh(self):
        """
        close the SSH connection if relevant
        """
        if self.conn is not None:
            preserve = self.conn
            self.conn = None
            try:
                preserve.close()
            except Exception:
                pass

            await preserve.wait_closed()
            if self.client._connection_lost:
                raise ConnectionError("Close connection went wrong")
    async def close(self):
        """
        Close everything open, i.e. ssh connection and SFTP subsystem
        """
        # beware that when used with asynciojobs, we often have several jobs
        # sharing the same proxy, and so there might be several calls to
        # close() sent to the same object at the same time...
        async with self._disconnect_lock:
            await self._close_sftp()
            await self._close_ssh()

    ##############################
    async def run(self, command, **x11_kwds):
        """
        Run a command, and write its output on the fly
        according to instance's formatter.

        Parameters:
          command: remote command to run
          x11_kwds: optional keyword args that will be passed
            to create_session, like typically ``x11_forwarding=True``

        Returns:
          remote command exit status - or None if nothing could be run at all

        """

        # pylint: disable=c0111
        # this closure is a _LineBasedSession
        # with a .proxy attribute that points back here
        class SessionClosure(_LineBasedSession):
            # not using 'self' because 'self' is the SshProxy instance already
            def __init__(session_self, *args, **kwds):  # pylint: disable=e0213
                _LineBasedSession.__init__(
                    session_self, self, command, *args, **kwds)

        chan, session = \
            await asyncio.wait_for(
                self.conn.create_session(SessionClosure, command, **x11_kwds),
                timeout=self.timeout)
        await chan.wait_closed()
        return session._exit                          # pylint: disable=w0212

    async def mkdir(self, remotedir):
        """
        Create a remote directory if needed.

        Parameters:
          remotedir(str): remote repository to create.

        Returns:
          True if remote directory existed or could be created,
          False if SFTP subsystem could not be set up.

        Raises:
          asyncssh.sftp.SFTPError

        """
        if not await self.sftp_connect_lazy():
            return False
        exists = await self.sftp_client.isdir(remotedir)
        if exists:
            self.debug_line(
                "{} already exists - no need to create".format(remotedir))
            return True
        try:
            self.debug_line("actual creation of {}".format(remotedir))
            await self.sftp_client.mkdir(remotedir)
            return True
        except asyncssh.sftp.SFTPError as exc:
            self.debug_line(
                "Could not create {} on {}\n{}".format(remotedir, self, exc))
            raise exc

    # shows up first in doc
    async def get_file_s(self, remotepaths, localpath, **kwds):
        """
        Retrieve a collection of remote files locally into the same directory.
        The ssh connection and SFTP subsystem are created and set up if needed.

        Parameters:
          remotepaths(list): remote files to retrieve
          localpath: where to store them
          kwds: passed along to the underlying asyncssh's sftp client,
            typically: ``preserve``, ``recurse`` and ``follow_symlinks``
            are honored like in
            http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.get

        Returns:
          True if all went well, or raise exception
        """
        await self.sftp_connect_lazy()
        try:
            self.debug_line(
                "doing SFTP get with {} -> {}".format(remotepaths, localpath))
            await self.sftp_client.get(remotepaths, localpath, **kwds)
        except asyncssh.sftp.SFTPError as exc:
            self.debug_line(
                "Could not SFTP GET remotes {} to local {} - exception={}".
                format(remotepaths, localpath, exc))
            raise exc
        return True

    async def put_file_s(self, localpaths, remotepath, **kwds):

        """
        Copy a collection of local files remotely into the same directory.
        The ssh connection and SFTP subsystem are created and set up if needed.

        Parameters:
          localpaths (list): files to copy
          remotepath (str): where to copy
          kwds: passed along to the underlying asyncssh's sftp client,
            typically: ``preserve``, ``recurse`` and ``follow_symlinks``
            are honored like in
            http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.put

        Returns:
          True if all went well, or raise exception
        """
        await self.sftp_connect_lazy()
        try:
            self.debug_line(
                "doing SFTP put with {} -> {}".format(localpaths, remotepath))
            await self.sftp_client.put(localpaths, remotepath, **kwds)
        except asyncssh.sftp.SFTPError as exc:
            self.debug_line(
                "Could not SFTP PUT local {} to remote {} - exception={}".
                format(localpaths, remotepath, exc))
            raise exc
        return True

    async def put_string_script(self, script_body, remotefile, **kwds):
        """
        A convenience for copying over a local script before remote execution.
        The ssh connection and SFTP subsystem are created and set up if needed.
        Resulting remote file has mode `755`.

        Parameters:
          script_body (str): the **contents** of the script to create
            **WARNING** this is **not** a filename.
          remotefile: filename on the remote end
          kwds: passed along to
            http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.open
            i.e. for setting ``encoding`` or ``errors``.

        Returns:
          True if all went well, or raise exception
        """
        await self.sftp_connect_lazy()
        sftp_attrs = asyncssh.SFTPAttrs()
        sftp_attrs.permissions = 0o755
        try:
            async with self.sftp_client.open(remotefile, pflags_or_mode='w',
                                             attrs=sftp_attrs,
                                             **kwds) as writer:
                await writer.write(script_body)
        except Exception as exc:
            self.debug_line("Could not create remotefile {} - exception={}"
                            .format(remotefile, exc))
            raise exc
        return True

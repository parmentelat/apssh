#!/usr/bin/env python3

import asyncio
import socket

import asyncssh

from .util import print_stderr, check_arg_type
from .config import default_remote_workdir
# a dummy formatter
from .formatters import Formatter, ColonFormatter


class _LineBasedSession(asyncssh.SSHClientSession):
    """
    a session that records both outputs (out and err) in its internal attributes
    it also may have an associated formatter (through its proxy reference)
    and in that case the formatter receives a line() call each time a line is received
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

        def data_received(self, data, datatype):
            # preserve it before any postprocessing occurs
            self.buffer += data
            # not adding a \n since it's already in there
            if self.proxy.debug:
                print_stderr('BS {} DR: -> {} [[of type {}]]'.
                             format(self.proxy.hostname, data, self.name))
            chunks = [x for x in data.split("\n")]
            # len(chunks) cannot be 0
            assert len(chunks) > 0, "unexpected data received"
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
                self.proxy.formatter.line(self.line, datatype, self.proxy.hostname)
                self.line = ""

    ##########
    def __init__(self, proxy, command, *args, **kwds):
        # self.proxy is expected to be set already by the closure/subclass
        self.proxy = proxy
        self.command = command
        self.stdout = self.Channel("stdout", proxy)
        self.stderr = self.Channel("stderr", proxy)
        self._status = None
        super().__init__(*args, **kwds)

    # this seems right only for text streams...
    def data_received(self, data, datatype):
        channel = self.stderr if datatype == asyncssh.EXTENDED_DATA_STDERR else self.stdout
        channel.data_received(data, datatype)

    def connection_made(self, conn):
        self.proxy.formatter.session_start(self.proxy.hostname, self.command)

    def connection_lost(self, exc):
        self.proxy.formatter.session_stop(self.proxy.hostname, self.command)

    def eof_received(self):
        self.stdout.flush(None, newline=False)
        self.stderr.flush(asyncssh.EXTENDED_DATA_STDERR, newline=False)
        self.proxy.debug_line("EOF")

    def exit_status_received(self, status):
        self._status = status
        self.proxy.debug_line("STATUS = {}\n".format(status))

# VerboseClient is created through factories attached to each proxy


class VerboseClient(asyncssh.SSHClient):

    def __init__(self, proxy, direct, *args, **kwds):
        self.proxy = proxy
        self.formatter = proxy.formatter
        self.direct = direct
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

    def auth_completed(self):
        self.formatter.auth_completed(self.proxy.hostname, self.proxy.username)

####################


class SshProxy:
    """
    a proxy that can connect to a remote, and then can run
    several commands in the most general sense, i.e. including file transfers

    its attached formatter is in charge of capturing the output of these commands.
    default is to use a `ColonFormatter` that displays hostname:actual-output

    the verbose flag allows to get some user-level feedback on ssh negociation
    permission denied messages and similar won't show up unless verbose is set

    The gateway parameter, when set, is another `SshProxy` instance, that is then used
    as a proxy for tunnelling a 2-leg ssh connection.

    """

    def __init__(self, hostname, username=None, known_hosts=None, keys=None, port=22,
                 gateway=None,  # if another SshProxy is given, it is used as an ssh gateway
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
        self.formatter = formatter or ColonFormatter("")
        if verbose is not None:
            self.formatter.verbose = verbose
        self.debug = debug
        self.timeout = timeout
        #
        self.conn, self.sftp_client = None, None
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
        return "<SshProxy {}>".format(text)

    def debug_line(self, line):
        if line.endswith("\n"):
            line = line[:-1]
        line += " ((from:" + repr(self) + "))\n"
        if self.debug:
            self.formatter.line(
                line, asyncssh.EXTENDED_DATA_STDERR, self.hostname)

    def is_connected(self):
        return self.conn is not None

    async def connect_lazy(self):
        """
        Connect if needed - uses a lock to ensure only one connection will 
        take place even if several calls are done at the same time
        """
        async with self._connect_lock:
            if self.conn is None:
                await self._connect()
            return self.conn

    async def _connect(self):
        """
        Unconditionnaly attemps to connect and raise an exception otherwise
        """
        if not self.gateway:
            return await self._connect_direct()
        else:
            return await self._connect_tunnel()

    async def _connect_direct(self):
        """
        The code for connecting to the first ssh hop (i.e. when self.gateway is None)
        """
        assert self.gateway is None

        class client_closure(VerboseClient):
            def __init__(client_self, *args, **kwds):
                VerboseClient.__init__(
                    client_self, self, direct=True, *args, **kwds)

        self.debug_line("SSH direct connecting")
        self.conn, client = \
            await asyncio.wait_for(
                asyncssh.create_connection(
                    client_closure, self.hostname, port=self.port, username=self.username,
                    known_hosts=self.known_hosts, client_keys=self.keys
                ),
                timeout=self.timeout)

    async def _connect_tunnel(self):
        """
        The code to connect to a higher-degree hop
        We expect gateway to have its connection open, and issue connect_ssh on that connection
        """
        # make sure the gateway has connected already
        assert self.gateway is not None
        await self.gateway.connect_lazy()

        class client_closure(VerboseClient):
            def __init__(client_self, *args, **kwds):
                VerboseClient.__init__(
                    client_self, self, direct=False, *args, **kwds)

        self.debug_line("SSH tunnel connecting")
        self.conn, client = \
            await asyncio.wait_for(
                self.gateway.conn.create_ssh_connection(
                    client_closure, self.hostname, port=self.port, username=self.username,
                    known_hosts=self.known_hosts, client_keys=self.keys
                ),
                timeout=self.timeout)
        self.debug_line("SSH tunnel connected")

    def is_sftp_connected(self):
        return self.sftp_client is not None

    async def sftp_connect_lazy(self):
        """
        Initializes SFTP connection if needed
        Returns True if sftp client is ready to be used, False otherwise
        """

        await self.connect_lazy()
        async with self._connect_lock:
            if self.sftp_client is None:
                await self._sftp_connect()
            return self.sftp_client

    async def _sftp_connect(self):
        if self.conn is None:
            return False
        self.sftp_client = await self.conn.start_sftp_client()
        self.formatter.sftp_start(self.hostname)

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
            except:
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
            except:
                pass
            await preserve.wait_closed()

    async def close(self):
        """
        close everything open
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
        Run a command, outputs it on the fly according to self.formatter
        and returns remote status - or None if nothing could be run at all

        x11_kwds are optional keyword args that will be passed to create_session
        like typically x11_forwarding=True
        """
        # this closure is a _LineBasedSession with a .proxy attribute that points back here
        class session_closure(_LineBasedSession):
            # not using 'self' because 'self' is the SshProxy instance already
            def __init__(session_self, *args, **kwds):
                _LineBasedSession.__init__(
                    session_self, self, command, *args, **kwds)

        # the idea here is to show a visible message in case someone
        # tries to use x11=True but has a too old version of apssh
        # OTOH we do not want this to trigger all the time..
        regular_mode = (not x11_kwds) \
            or (len(x11_kwds) == 1 and 'x11_forwarding' in x11_kwds and
                not x11_kwds['x11_forwarding'])
        if regular_mode:
            session_kwd_args = {}
        else:
            asyncssh_version_str = asyncssh.version.__version__
            asyncssh_version = [int(x)
                                for x in asyncssh_version_str.split('.')]
            if asyncssh_version > [1, 7, 3]:
                session_kwd_args = x11_kwds
            else:
                print(
                    "apssh: WARNING : need asyncssh > 1.7.3 to activate x11 forwarding - ignored")
                session_kwd_args = {}
        #
        chan, session = \
            await asyncio.wait_for(
                self.conn.create_session(
                    session_closure, command, **session_kwd_args),
                timeout=self.timeout)
        await chan.wait_closed()
        return session._status

    async def mkdir(self, remotedir):
        if not await self.sftp_connect_lazy():
            return False
        exists = await self.sftp_client.isdir(remotedir)
        if exists:
            self.debug_line(
                "{} already exists - no need to create".format(remotedir))
            return True
        try:
            self.debug_line("actual creation of {}".format(remotedir))
            retcod = await self.sftp_client.mkdir(remotedir)
            return True
        except asyncssh.sftp.SFTPError as e:
            self.debug_line(
                "Could not create {} on {}\n{}".format(remotedir, self, e))
            raise e

    async def put_file_s(self, localpaths, remotepath, *args, **kwds):

        """
        if needed, opens the ssh connection and SFTP subsystem
        put a local file - or files - as a remote

        args and kwds are passed along to the underlying asyncssh's sftp client
        typically: preserve, recurse and follow_symlinks are honored like in 

        http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.put

        returns True if all went well, or raise exception
        """
        sftp_connected = await self.sftp_connect_lazy()
        try:
            self.debug_line(
                "Running SFTP put with {} -> {}".format(localpaths, remotepath))
            await self.sftp_client.put(localpaths, remotepath, *args, **kwds)
        except asyncssh.sftp.SFTPError as e:
            self.debug_line("Could not SFTP PUT local {} to remote {} - exception={}".
                            format(localpaths, remotepath, e))
            raise e
        return True

    async def get_file_s(self, remotepaths, localpath, *args, **kwds):
        """
        identical to put_file_s but the other way around
        can use asyncssh's SFTP client get options as well

        http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.get
        """
        sftp_connected = await self.sftp_connect_lazy()
        try:
            self.debug_line(
                "Running SFTP get with {} -> {}".format(remotepaths, localpath))
            await self.sftp_client.get(remotepaths, localpath, *args, **kwds)
        except asyncssh.sftp.SFTPError as e:
            self.debug_line("Could not SFTP GET remotes {} to local {} - exception={}".
                            format(remotepaths, localpath, e))
            raise e
        return True

    async def put_string_script(self, script_body, remotefile, *args, **kwds):
        """
        creates remotefile and uses script_body as its contents
        also chmod's remotefile to 755
        """
        sftp_connected = self.sftp_connect_lazy()
        sftp_attrs = asyncssh.SFTPAttrs()
        sftp_attrs.permissions = 0o755
        try:
            async with self.sftp_client.open(remotefile, pflags_or_mode='w',
                                             attrs=sftp_attrs, *args, **kwds) as writer:
                await writer.write(script_body)
        except Exception as e:
            self.debug_line("Could not create remotefile {} - exception={}"
                            .format(remotefile, e))
            raise e
        return True

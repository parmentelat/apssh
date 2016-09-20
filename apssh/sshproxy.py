#!/usr/bin/env python3

import os.path
import asyncio
import asyncssh
import socket

from .util import print_stderr
from .config import default_remote_workdir
# a dummy formatter
from .formatters import Formatter

class LineBasedSession(asyncssh.SSHClientSession):
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
            self.hostname = proxy.hostname
            self.formatter = proxy.formatter
            self.debug = proxy.debug
            self.buffer = ""
            self.line = ""
            
        def data_received(self, data, datatype):
            # preserve it before any postprocessing occurs
            self.buffer += data
            # not adding a \n since it's already in there
            if self.debug:
                print_stderr('BS {} DR: -> {} [[of type {}]]'.
                             format(self.hostname, data, self.name))
            chunks = [ x for x in data.split("\n") ]
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
                self.formatter.line(self.line, datatype, self.hostname)
                self.line = ""

    ##########
    def __init__(self, *args, **kwds):
        # self.proxy is expected to be set already by the closure/subclass
        self.stdout = self.Channel("stdout", self.proxy)
        self.stderr = self.Channel("stderr", self.proxy)
        self._status = None
        super().__init__(*args, **kwds)

    # this seems right only for text streams...
    def data_received(self, data, datatype):
        channel = self.stderr if datatype == asyncssh.EXTENDED_DATA_STDERR else self.stdout
        channel.data_received(data, datatype)

    def connection_made(self, conn):
        if self.proxy.debug:
            print_stderr('BS {} CM: {}'.format(self.proxy, conn))
        pass

    def connection_lost(self, exc):
        if self.proxy.debug:
            print_stderr('BS {} CL: exc={}'.format(self.proxy, exc))
        pass

    def eof_received(self):
        if self.proxy.debug:
            print_stderr('BS {} EOF'.format(self.proxy))
        self.stdout.flush(None, newline=False)
        self.stderr.flush(asyncssh.EXTENDED_DATA_STDERR, newline=False)
        if self.proxy.formatter:
            self.proxy.formatter.session_stop(self.proxy.hostname)

    def exit_status_received(self, status):
        if self.proxy.debug:
            print_stderr("BS {} ESR {}".format(self.proxy, status))
        self._status = status

class VerboseClient(asyncssh.SSHClient):
    def connection_made(self, conn):
        self.ip = conn.get_extra_info('peername')[0]
        if self.proxy.debug:
            print_stderr('VC Connection made to {}'.format(self.ip))

    # xxx we don't get this; at least, not always
    # the issue seems to be that we use close() on the asyncssh connection
    # which is a synchroneous call and I am not sure
    # for what other future I should await instead/afterwards
    # this actually triggers though occasionnally esp. with several targets
    def connection_lost(self, exc):
        if self.proxy.debug:
            print_stderr('VC Connection lost to {} (exc={})'.format(self.ip, exc))

    def auth_completed(self):
        if self.proxy.debug:
            print_stderr('VC Authentication successful on {}.'.format(self.ip))

####################
class SshProxy:
    """
    a proxy that can connect to a remote, and then can run
    several commands - a.k.a. sessions
    formatter - see formatters.py 
    """
    def __init__(self, hostname, username=None, known_hosts=None, client_keys=None, port=22,
                 gateway=None, # if another SshProxy is given, it is used as an ssh gateway
                 formatter=None, debug=False, timeout=30):
        self.hostname = hostname
        self.username = username
        self.known_hosts = known_hosts
        self.client_keys = client_keys if client_keys is not None else []
        self.port = int(port)
        self.gateway = gateway
        # if not specified we use a totally dummy and mostly silent formatter
        self.formatter = formatter or Formatter()
        self.debug = debug
        self.timeout = timeout
        #
        self.conn, self.sftp_client = None, None
        # critical sections require mutual exclusions
        self._connect_lock = asyncio.Lock()
        self._disconnect_lock = asyncio.Lock()

    def __user_host__(self):
        return "{}@{}".format(self.username, self.hostname) if self.username \
            else "@" + self.hostname

    def __repr__(self):
        text = "" if not self.gateway \
               else "{} <--> ".format(self.gateway.__user_host__())
        text += self.__user_host__()
        text += " [{}]".format(type(self.formatter).__name__)
        if self.conn:
            text += "<-SSH->"
        if self.sftp_client:
            text += "<-SFTP->"
        return "<SshProxy {}>".format(text)
    
    async def connect_lazy(self):
        """
        Connect if needed - uses a lock to ensure only one connection will 
        take place even if several calls are done at the same time
        """
        with (await self._connect_lock):
            if self.conn is None:
                await self._connect()
            return self.conn
            
    async def _connect(self):
        """
        Unconditionnaly attemps to connect and raise an exception otherwise
        """
        try:
            if not self.gateway:
                return await self._connect_direct()
            else:
                return await self._connect_tunnel()
        except (OSError, asyncssh.Error, asyncio.TimeoutError, socket.gaierror) as e:
            self.formatter.connection_failed(self.hostname, self.username, self.port, e)
            raise e
        
    async def _connect_direct(self):
        """
        The code for connecting to the first ssh hop (i.e. when self.gateway is None)
        """
        assert self.gateway is None
        if self.debug:
            print_stderr("{} 1st hop CONNECTING".format(self))

        class client_closure(VerboseClient):
            def __init__(client_self, *args, **kwds):
                client_self.proxy = self
                super().__init__(*args, **kwds)

        self.conn, client = \
            await asyncio.wait_for( 
                asyncssh.create_connection(
                    client_closure, self.hostname, port=self.port, username=self.username,
                    known_hosts=self.known_hosts, client_keys=self.client_keys
                ),
                timeout = self.timeout)
        self.formatter.connection_start(self.hostname, direct=True)
        if self.debug:
            print_stderr("{} 1st hop CONNECTED".format(self))

    async def _connect_tunnel(self):
        """
        The code to connect to a higher-degree hop
        We expect gateway to have its connection open, and issue connect_ssh on that connection
        """
        # make sure the gateway has connected already
        assert self.gateway is not None
        await self.gateway.connect_lazy()
        if self.debug:
            print_stderr("{} remote CONNECTING".format(self))
        # XXX it looks like conn.connect_ssh won't let us define our factory
        # However we do not see any missing feature here, so somehow asyncssh
        # must do the right thing under the hood...
        self.conn = \
            await asyncio.wait_for(
                 self.gateway.conn.connect_ssh(
                     self.hostname, port=self.port, username=self.username,
                     known_hosts=self.known_hosts, client_keys=self.client_keys
                 ),
                 timeout = self.timeout)
        self.formatter.connection_start(self.hostname, direct=False)
        if self.debug:
            print_stderr("{} remote CONNECTED through {}".format(self, self.gateway))

    async def sftp_connect_lazy(self):
        await self.connect_lazy()
        with (await self._connect_lock):
            if self.sftp_client is None:
                await self._sftp_connect()
            return self.sftp_client
            
    async def _sftp_connect(self):
        """
        Initializes SFTP connection
        Returns True if sftp client is ready to be used, False otherwise
        """
        if self.conn is None:
            return False
        try:
            self.sftp_client = await self.conn.start_sftp_client()
        except (asyncssh.sftp.SFTPError, asyncio.TimeoutError) as e:
            self.formatter.connection_failed(self.hostname, self.username, self.port, e)
            raise e

    async def _close_sftp(self):
        """
        close the SFTP client if relevant
        """
        if self.sftp_client is not None:
            self.formatter.connection_stop(self.hostname)
            # set self.sftp_client to None *before* awaiting
            # to avoid duplicate attempts
            preserve = self.sftp_client
            self.sftp_client = None
            preserve.exit()
            await preserve.wait_closed()

    async def _close_ssh(self):
        """
        close the SSH connection if relevant
        """
        if self.conn is not None:
            if self.debug:
                print_stderr("{} DISCONNECTING".format(self))
            preserve = self.conn
            self.conn = None
            preserve.close()
            await preserve.wait_closed()

    async def close(self):
        """
        close everything open
        """
        # beware that when used with asynciojobs, we often have several jobs
        # sharing the same proxy, and so there might be several calls to
        # close() sent to the same object at the same time...
        with (await self._disconnect_lock):
            await self._close_sftp()
            await self._close_ssh()

    ##############################
    async def run(self, command):
        """
        Run a command, outputs it on the fly according to self.formatter
        and returns remote status - or None if nothing could be run at all
        """
        # this closure is a LineBasedSession with a .proxy attribute that points back here
        class session_closure(LineBasedSession):
            # not using 'self' because 'self' is the SshProxy instance already
            def __init__(session_self, *args, **kwds):
                session_self.proxy = self
                super().__init__(*args, **kwds)

        try:
            if self.debug:
                print_stderr("{}: sending command {}".format(self, command))
            chan, session = \
                await asyncio.wait_for(
                    self.conn.create_session(session_closure, command),
                    timeout=self.timeout)
            # xxx need to make sure this is clean
            formatter_command = command.replace('>', '..').replace('<', '..')
            self.formatter.session_start(self.hostname, formatter_command)
            await chan.wait_closed()
            return session._status
        except asyncio.TimeoutError as e:
            self.formatter.session_failed(self.hostname, command, ("UNHANDLED", e))
            raise e

    async def mkdir(self, remotedir):
        if not await self.sftp_connect_lazy():
            return False
        exists = await self.sftp_client.isdir(remotedir)
        if exists:
            if self.debug:
                print_stderr("{} mkdir: {} already exists".format(self, remotedir))
            return True
            exit(0)
        try:
            if self.debug:
                print_stderr("{} mkdir: actual creation of {}".format(self, remotedir))
            retcod = await self.sftp_client.mkdir(remotedir)
            return True
        except asyncssh.sftp.SFTPError as e:
            if self.debug:
                print_stderr("Could not create {} on {}".format(default_remote_workdir, self))
            raise e

    async def install_script(self, localpath, remotepath,
                             follow_symlinks=False, preserve=True, disconnect=False):
        """
        opens a connection if needed
        opens a SFTP connection if needed
        install a local file as a remote (remote is set as executable if source is)
        * preserve: if True, copy will preserve access, modtimes and permissions
        * follow_symlinks: if False, symlinks get created on the remote end
        * disconnect: tear down connections (ssh and sftp) if True

        returns True if all went well, False otherwise
        """
        # half full glass; only one branch that leads to success
        retcod = False
        sftp_connected = await self.sftp_connect_lazy()
        if sftp_connected:
            if self.debug:
                print_stderr("{} : Running SFTP put with {} -> {}"
                             .format(self, localpath, remotepath))
            put_result = await self.sftp_client.put(localpath, remotepath, preserve=preserve,
                                                    follow_symlinks=follow_symlinks)
            if self.debug:
                print_stderr("put returned {}".format(put_result))
            return True

    #################### high level helpers for direct use in apssh or jobs
    # regarding exceptions, the most convenient approach is for
    # jobs to raise an exception when something serious happens
    async def connect_run(self, command, disconnect=True):
        """
        This helper function will connect if needed, run a command
        also disconnect (close connection) if requested - default is on
        returns 
        """
        connected = await self.connect_lazy()
        if connected:
            # xxx protect here with timeout / wait_for ???
            data = await self.run(command)
            if disconnect:
                await self.close()
            return data

    async def connect_install_run(self, localfile, *script_args, disconnect=True):
        """
        This helper function does everything needed to push a script remotely
        and run it; which involves
        * creating a remote subdir {}
        * pushing local file in there
        * remote run in the home directory the command with 
          .apssh/basename
        returns either
        * a retcod (0 for success, other wait code otherwise) if the command can be run
        * None otherwise (host not reachable, or other serious failure)
        """
        connected = await self.sftp_connect_lazy()
        if not connected:
            return None
        # create .apssh remotely
        if not await self.mkdir(default_remote_workdir):
            return None
        # install local file remotely
        if not await self.install_script(localfile, default_remote_workdir):
            return None
        # run it
        basename = os.path.basename(localfile)
        # accept integers and the like
        extras = " ".join(str(arg) for arg in script_args)
        command = "{}/{} {}".format(default_remote_workdir, basename, extras)
        result = await self.run(command)
        return result

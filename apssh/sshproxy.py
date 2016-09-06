#!/usr/bin/env python3

import os.path
import asyncio
import asyncssh
import socket

from .util import print_stderr
from .config import default_remote_workdir

class BufferedSession(asyncssh.SSHClientSession):
    """
    a session that records all outputs in its buffer internal attribute
    """
    def __init__(self, *args, **kwds):
        self._buffer = ""
        self._line = ""
        self._status = None
        super().__init__(*args, **kwds)

    def flush_line(self):
        if self.proxy.formatter:
            self._line += "\n"
            self.proxy.formatter.line(self.proxy.hostname, self._line)
            self._line = ""

    # this seems right only for text streams...
    def data_received(self, data, datatype):
        self._buffer += data
        # not adding a \n since it's already in there
        if self.proxy.debug:
            print_stderr('BS {} DR: -> {} [[of type {}]]'.
                         format(self.proxy, data, datatype))
        chunks = [ x for x in data.split("\n") ]
        # len(chunks) cannot be 0
        assert len(chunks) > 0, "unexpected data received"
        # no newline in received data
        same_line = chunks.pop(0)
        self._line += same_line
        for chunk in chunks:
            self.flush_line()
            self._line = chunk

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
        if self._line:
            self.flush_line()
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
    def __init__(self, hostname, username=None, known_hosts=None, client_keys=None,
                 port=22, formatter=None, debug=False, timeout=30):
        self.hostname = hostname
        self.username = username
        self.known_hosts = known_hosts
        self.client_keys = client_keys if client_keys is not None else []
        self.port = int(port)
        self.formatter = formatter
        self.debug = debug
        self.timeout = timeout
        #
        self.conn, self.client, self.sftp_client = None, None, None

    def __repr__(self):
        text = "{}@{}".format(self.username, self.hostname) if self.username else "@"+self.hostname
        if self.formatter:
            text += " [{}]".format(type(self.formatter).__name__)
        if self.conn:
            text += "<-SSH->"
        if self.sftp_client:
            text += "<-SFTP->"
        return "<SshProxy {}>".format(text)
    
    async def connect_lazy(self):
        if self.conn is None:
            await self.connect()
        return self.conn
            
    async def connect(self):
        try:
            if self.debug:
                print_stderr("{} CONNECTING".format(self))
            class client_closure(VerboseClient):
                def __init__(client_self, *args, **kwds):
                    client_self.proxy = self
                    super().__init__(*args, **kwds)

            self.conn, self.client = \
                await asyncio.wait_for( 
                    asyncssh.create_connection(
                        client_closure, self.hostname, port=self.port, username=self.username,
                        known_hosts=self.known_hosts, client_keys=self.client_keys
                    ),
                    timeout = self.timeout)
            if self.formatter:
                self.formatter.connection_start(self.hostname)
            if self.debug:
                print_stderr("{} CONNECTED".format(self))
            return True
        except (OSError, asyncssh.Error, asyncio.TimeoutError, socket.gaierror) as e:
            self.formatter.connection_failed(self.hostname, self.username, self.port, e)
            self.conn, self.client = None, None
            return False
        except Exception as e:
            print_stderr("Unexpected exception in create_connection {}".format(e))
            self.formatter.connection_failed(self.hostname, self.username, self.port, ("UNHANDLED", e))
            self.conn, self.client = None, None
            return False

    async def sftp_connect_lazy(self):
        if self.sftp_client is None:
            await self.sftp_connect()
        return self.sftp_client
            
    async def sftp_connect(self):
        """
        Performs connection if needed, and initializes SFTP connection
        Returns True if sftp client is ready to be used, False otherwise
        """
        connected = await self.connect_lazy()
        if not connected:
            return False
        try:
            self.sftp_client = await self.conn.start_sftp_client()
        except asyncssh.sftp.SFTPError:
            if self.debug:
                print_stderr("FAILED to start_sftp_client")
            self.sftp_client = None
        if self.debug:
            print_stderr("AFTER start_sftp_client -> {}".format(self.sftp_client))
        return self.sftp_client is not None

    async def sftp_close(self):
        if self.sftp_client is not None:
            # xxx use return code ?
            await self.sftp_client.wait_closed()
            self.sftp_client = None

    async def close(self):
        await self.sftp_close()
        if self.conn is not None:
            self.conn.close()
            await self.conn.wait_closed()
            self.conn, self.client = None, None

    ##############################
    async def run(self, command):
        """
        Run a command, outputs it on the fly according to self.formatter
        and returns remote status - or None if nothing could be run at all
        """
        # this closure is a BufferedSession with a .proxy attribute that points back here
        class session_closure(BufferedSession):
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
            if self.formatter:
                self.formatter.session_start(self.hostname,
                                             formatter_command)
            await chan.wait_closed()
            return session._status
        except asyncio.TimeoutError as e:
            self.formatter.session_failed(self.hostname, command, ("UNHANDLED", e))
        # also seen here : asyncssh.misc.ChannelOpenError
        except Exception as e:
            self.formatter.session_failed(self.hostname, command, ("UNHANDLED", e))
            return

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
            try:
                if self.debug:
                    print_stderr("{} : Running SFTP put with {} -> {}"
                                 .format(self, localpath, remotepath))
                put_result = await self.sftp_client.put(localpath, remotepath, preserve=preserve,
                                                        follow_symlinks=follow_symlinks)
                if self.debug:
                    print_stderr("put returned {}".format(put_result))
                retcod = True
            except OSError as e:
                print("OSError", e)
            except asyncssh.sftp.SFTPError as e:
                print("SFTPError", e)
            except Exception as e:
                import traceback
                traceback.print_exc()
            if disconnect:
                await self.close()
        return retcod

    # hight level helpers for direct use in apssh
    async def connect_and_run(self, command, disconnect=True):
        """
        This helper function will connect if needed, run a command
        also disconnect (close connection) if requested - default is on
        returns 
        """
        connected = await self.connect_lazy()
        if connected:
            # xxx protect here with timeout / wait_for
            data = await self.run(command)
            if disconnect:
                await self.close()
            return data

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
            return False

    async def connect_put_and_run(self, localfile, *args, disconnect=True):
        """
        This helper function does everything needed to push a script remotely
        and run it; which involves
        * creating a remote subdir {}
        * pushing local file in there
        * remote run in this same directory the command with 
          cd {}; ./basename
        returns either
        * a retcod (0 for success, other wait code otherwise) if the command can be run
        * None otherwise (host not reachable, or other serious failure)
        """
        print(" ARGS = ", args)
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
        extras = " ".join(args)
        command = "cd {}; ./{} {}".format(default_remote_workdir, basename, extras)
        result = await self.run(command)
        return result

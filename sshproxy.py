#!/usr/bin/env python3

import asyncio
import asyncssh

debug = False
#debug = True

class BufferedSession(asyncssh.SSHClientSession):
    """
    a session that records all outputs in its buffer internal attribute
    """
    def __init__(self, *args, **kwds):
        self.buffer = ""
        super().__init__(*args, **kwds)

    def data_received(self, data, datatype):
        # not adding a \n since it's already in there
        if debug: print('BS DR: -> {} [[of type {}]]'.
                        format(data, datatype))
        self.buffer += data
        # xxx temporary - should split lines instead
        if self.proxy.formatter:
            self.proxy.formatter.line(self.proxy.hostname, data)

    def connection_made(self, conn):
        if debug: print('BS CM: {}'.format(conn))
        pass

    def connection_lost(self, exc):
        if exc:
            if debug: print('BS CL: exc={}'.format(exc))
        pass

    def eof_received(self):
        if debug: print('BS EOF')
        if self.proxy.formatter:
            self.proxy.formatter.session_stop(self.proxy.hostname)


class MyClient(asyncssh.SSHClient):
    def connection_made(self, conn):
        self.ip = conn.get_extra_info('peername')[0]
        if debug: print('SSC Connection made to {}.'.format(self.ip))

    def auth_completed(self):
        if debug: print('SSC Authentication successful on {}.'.format(self.ip))

####################
class SshProxy:
    """
    a proxy that can connect to a remote, and then can run
    several commands - a.k.a. sessions
    formatter - see formatters.py 
    """
    def __init__(self, hostname, username=None, known_hosts=None, client_keys=None,
                 port=22, formatter=None):
        self.hostname = hostname
        self.username = username
        self.known_hosts = known_hosts
        self.client_keys = client_keys if client_keys is not None else []
        self.port = int(port)
        self.formatter = formatter
        #
        self.conn, self.client = None, None

    def __repr__(self):
        text = "{}@{}".format(self.username, self.hostname) if self.username else "@"+self.hostname
        if self.formatter:
            text += " [{}]".format(type(self.formatter).__name__)
        return "<SshProxy {}>".format(text)
    
    async def connect(self):
        try:
            if debug: print("connecting to", self)
            # see http://asyncssh.readthedocs.org/en/latest/api.html#specifyingprivatekeys
            self.conn, self.client = await asyncssh.create_connection(
                MyClient, self.hostname, port=self.port, username=self.username,
                known_hosts=self.known_hosts, client_keys=self.client_keys
            )
            if self.formatter:
                self.formatter.connection_start(self.hostname)
            if debug: print("connected to", self)
            return True
        except (OSError, asyncssh.Error) as e:
            # print('ssh connection failed: {}'.format(e))
            self.conn, self.client = None, None
            return False

    async def run(self, command):
        """
        Run a command, outputs it on the fly according to self.formatter
        and returns the whole output
        """
        # this closure is a BufferedSession with a .proxy attribute that points back here
        class session_closure(BufferedSession):
            def __init__(session_self, *args, **kwds):
                session_self.proxy = self
                super().__init__(*args, **kwds)

        try:
            if debug: print("{}: sending command {}".format(self, command))
            chan, session = await self.conn.create_session(session_closure, command)
            # xxx need to make sure this is clean
            formatter_command = command.replace('>', '..').replace('<', '..')
            if self.formatter:
                self.formatter.session_start(self.hostname,
                                             formatter_command)
            await chan.wait_closed()
            if debug: print("{}: command {} returned {}".format(self, command, session.buffer))
            return session.buffer
        except:
            import traceback
            traceback.print_exc()
            return

    async def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    async def connect_and_run(self, command):
        connected = await self.connect()
        if connected:
            data = await self.run(command)
            await self.close()
            return data

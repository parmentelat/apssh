#!/usr/bin/env python3

import asyncio
import asyncssh

class BufferedSession(asyncssh.SSHClientSession):
    """
    a session that records all outputs in its buffer internal attribute
    """
    def __init__(self, *args, **kwds):
        self._buffer = ""
        self._line = ""
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
        if self.proxy.debug: print('BS DR: -> {} [[of type {}]]'.format(data, datatype))
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
        if self.proxy.debug: print('BS CM: {}'.format(conn))
        pass

    def connection_lost(self, exc):
        if self.proxy.debug: print('BS CL: exc={}'.format(exc))
        pass

    def eof_received(self):
        if self.proxy.debug: print('BS EOF')
        if self._line:
            self.flush_line()
        if self.proxy.formatter:
            self.proxy.formatter.session_stop(self.proxy.hostname)


class VerboseClient(asyncssh.SSHClient):
    def connection_made(self, conn):
        self.ip = conn.get_extra_info('peername')[0]
        if self.proxy.debug: print('VC Connection made to {}'.format(self.ip))

    # xxx we don't get this; at least, not always
    # the issue seems to be that we use close() on the asyncssh connection
    # which is a synchroneous call and I am not sure
    # for what other future I should await instead/afterwards
    # this actually triggers though occasionnally esp. with several targets
    def connection_lost(self, exc):
        if self.proxy.debug: print('VC Connection lost to {} (exc={})'.format(self.ip, exc))

    def auth_completed(self):
        if self.proxy.debug: print('VC Authentication successful on {}.'.format(self.ip))

####################
class SshProxy:
    """
    a proxy that can connect to a remote, and then can run
    several commands - a.k.a. sessions
    formatter - see formatters.py 
    """
    def __init__(self, hostname, username=None, known_hosts=None, client_keys=None,
                 port=22, formatter=None, debug=False):
        self.hostname = hostname
        self.username = username
        self.known_hosts = known_hosts
        self.client_keys = client_keys if client_keys is not None else []
        self.port = int(port)
        self.formatter = formatter
        #
        self.conn, self.client = None, None
        self.debug = debug

    def __repr__(self):
        text = "{}@{}".format(self.username, self.hostname) if self.username else "@"+self.hostname
        if self.formatter:
            text += " [{}]".format(type(self.formatter).__name__)
        return "<SshProxy {}>".format(text)
    
    async def connect(self):
        try:
            if self.debug: print("{} connecting".format(self))
            class client_closure(VerboseClient):
                def __init__(client_self, *args, **kwds):
                    client_self.proxy = self
                    super().__init__(*args, **kwds)

            # see http://asyncssh.readthedocs.org/en/latest/api.html#specifyingprivatekeys
            self.conn, self.client = await asyncssh.create_connection(
                client_closure, self.hostname, port=self.port, username=self.username,
                known_hosts=self.known_hosts, client_keys=self.client_keys
            )
            if self.formatter:
                self.formatter.connection_start(self.hostname)
            if self.debug: print("{} connected".format(self))
            return True
        except (OSError, asyncssh.Error) as e:
            self.formatter.connection_failed(self.hostname, self.username, self.port, e)
            self.conn, self.client = None, None
            return False

    async def run(self, command):
        """
        Run a command, outputs it on the fly according to self.formatter
        and returns the whole output
        """
        # this closure is a BufferedSession with a .proxy attribute that points back here
        class session_closure(BufferedSession):
            # not using 'self' because 'self' is the SshProxy instance already
            def __init__(session_self, *args, **kwds):
                session_self.proxy = self
                super().__init__(*args, **kwds)

        try:
            if self.debug: print("{}: sending command {}".format(self, command))
            chan, session = await self.conn.create_session(session_closure, command)
            # xxx need to make sure this is clean
            formatter_command = command.replace('>', '..').replace('<', '..')
            if self.formatter:
                self.formatter.session_start(self.hostname,
                                             formatter_command)
            await chan.wait_closed()
            return session._buffer
        except:
            import traceback
            traceback.print_exc()
            return

    async def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn, self.client = None, None

    async def connect_and_run(self, command):
        connected = await self.connect()
        if connected:
            data = await self.run(command)
            await self.close()
            return data

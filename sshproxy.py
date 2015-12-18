#!/usr/bin/env python3

import asyncio
import asyncssh

debug = False
#debug = True

class MySession(asyncssh.SSHClientSession):
    def __init__(self, *args, **kwds):
        self.data = ""
        super().__init__(*args, **kwds)

    def data_received(self, data, datatype):
        # not adding a \n since it's already in there
        if debug: print('SSS DR: -> {} [[of type {}]]'.
                        format(data, datatype))
        self.data += data

    def connection_made(self, conn):
        if debug: print('SSS CM: {}'.format(conn))
        pass

    def connection_lost(self, exc):
        if exc:
            if debug: print('SSS CL: exc={}'.format(exc))
        pass

    def eof_received(self):
        if debug: print('SSS EOF')


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
    several commands
    XXX - todo
    xxx first draft mentions known_hosts=None, meaning this is not checked at all
    xxx no way to specify private key yet
    """
    def __init__(self, hostname, username=None, known_hosts=None, client_keys = None, port=22):
        self.hostname = hostname
        self.username = username
        self.known_hosts = known_hosts
        self.client_keys = client_keys if client_keys is not None else []
        self.port = int(port)
        #
        self.conn, self.client = None, None

    def __repr__(self):
        text = "{}@{}".format(self.username, self.hostname) if self.username else "@"+self.hostname
        return "<SshProxy {}>".format(text)
    
    async def connect(self):
        try:
            if debug: print("connecting to", self)
            # see http://asyncssh.readthedocs.org/en/latest/api.html#specifyingprivatekeys
            self.conn, self.client = await asyncssh.create_connection(
                MyClient, self.hostname, port=self.port, username=self.username,
                known_hosts=self.known_hosts, client_keys=self.client_keys
            )
            if debug: print("connected to", self)
            return True
        except (OSError, asyncssh.Error) as e:
            # print('ssh connection failed: {}'.format(e))
            self.conn, self.client = None, None
            return False

    async def run(self, command):
        """
        Run a command and return output in value

        """
        #print(5*'-', "running on ", self.hostname, ':', command)
        try:
            if debug: print("{}: sending command {}".format(self, command))
            chan, session = await self.conn.create_session(MySession, command)
            await chan.wait_closed()
            if debug: print("{}: command {} returned {}".format(self, command, session.data))
            return session.data
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

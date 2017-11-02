#!/usr/bin/python3

import os.path
from getpass import getpass
import asyncio
import asyncssh

# this code for now simply handles the prompting of a key if specified on the
# command line but cannot be loaded without a psasphrase
#
# what the actual code should do is
# (*) try to reach an agent; if it can be found, use the keys it has in store
# (*) otherwise: use the current algorithm, i.e.
#  (**) use the keys specified on the command line - and only them
#  (**) or use ~/.ssh/id_rsa and/or ~/id_dsa otherwise
#  (**) and in any case use the following method to prompt for a passphrase
#
# it does not feel like a cache filename -> key-object is required but well...
# we must remember that it's an SshProxy object that requires a list of keys,
# so it's not quite clear yet if this caching will be needed or not

def import_private_key(filename):
    """
    Attempts to import a private key from file

    Prompts for a password if needed
    """
    sshkey = None
    basename = os.path.basename(filename)
    if not os.path.exists(filename):
        # print("No such key file {}".format(filename))
        return
    with open(filename) as file:
        data = file.read()
        try:
            sshkey = asyncssh.import_private_key(data)
        except asyncssh.KeyImportError:
            while True:
                passphrase = getpass("Enter passphrase for key {} : ".format(basename))
                if not passphrase:
                    print("Ignoring key {}".format(filename))
                    break
                try:
                    sshkey = asyncssh.import_private_key(data, passphrase)
                    break
                except asyncssh.KeyImportError:
                    print("Wrong passphrase")
        except Exception as e:
            import traceback
            traceback.print_exc()
        return sshkey

def load_agent_keys(loop=None, agent_path=None):
    """
    returns a list of keys from the agent

    agent_path defaults to env. variable $SSH_AUTH_SOCK
    """
    async def co_load_agent_keys(loop, agent_path):
        # make sure to return an empty list when something goes wrong
        try:
            agent_client = asyncssh.SSHAgentClient(loop, agent_path)
            return await agent_client.get_keys()
        except Exception as e:
            # not quite sure which exceptions to expect here
            print("When fetching agent keys: ignored exception {}".format(e))
            return []
            

    agent_path = agent_path or os.environ.get('SSH_AUTH_SOCK', None)
    if agent_path is None:
        return []
    loop = loop or asyncio.get_event_loop()
    return loop.run_until_complete(co_load_agent_keys(loop, agent_path))

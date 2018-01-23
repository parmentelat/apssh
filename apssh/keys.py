#!/usr/bin/python3

import os
from pathlib import Path
from getpass import getpass
import asyncio
import asyncssh

from .config import default_private_keys


def import_private_key(filename):
    """
    Attempts to import a private key from file

    Prompts for a password if needed

    Returns a (asyncssh) key object if successful, or None
    """
    sshkey = None
    path = Path(filename)
    basename = path.name
    if not path.exists():
        # print("No such key file {}".format(filename))
        return
    with path.open() as file:
        data = file.read()
        try:
            sshkey = asyncssh.import_private_key(data)
        except asyncssh.KeyImportError:
            while True:
                passphrase = getpass(
                    "Enter passphrase for key {} : ".format(basename))
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


def load_private_keys(command_line_keys=None, verbose=False):
    """
    Here's how `apssh` locates private keys:

    * 1. If no keys are given as the command_line_keys parameter
         (typically through the apssh `-k` command line option)

      1.a if an *ssh agent* can be reached using the `SSH_AUTH_SOCK` environment variable,
        and offers a non-empty list of keys, `apssh` will use the keys loaded in the agent
        (**NOTE:** use `ssh-add` for managing the keys known to the agent)

      1.b otherwise, `apssh` will use `~/.ssh/id_rsa` and `~/.ssh/id_dsa` if existent

    * 2. If keys are specified on the command line

      2.c That exact list is used for loading private keys
    """
    filenames = []
    if not command_line_keys:
        agent_keys = load_agent_keys()
        # agent has stuff : let's use it
        if agent_keys:
            if verbose:
                print("apssh has loaded {} keys from the ssh agent"
                      .format(len(agent_keys)))
            return agent_keys
        # use config to figure out what the default keys are
        filenames = default_private_keys
        if verbose:
            print("apssh will try to load {} default keys".format(len(filenames)))
    else:
        filenames = command_line_keys
        if verbose:
            print("apssh will try to load {} keys from the command line".format(
                len(filenames)))
    keys = [import_private_key(filename) for filename in filenames]
    valid_keys = [k for k in keys if k]
    if verbose:
        print("apssh has loaded {} keys"
              .format(len(valid_keys)))
    return valid_keys

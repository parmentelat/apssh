#!/usr/bin/python3

"""
Basic tools for loading ssh keys from the user space or the agent
"""

import os
from pathlib import Path
from getpass import getpass
import asyncio
import asyncssh

from .config import default_private_keys


def import_private_key(filename):
    """
    This functions attempts to import a private key from its filename. It will
    prompt for a password if needed.

    Parameters:
      filename: the local path to the private key

    Returns:
      a (asyncssh) SSHKey_ object if successful, or None

    .. _SSHKey: http://asyncssh.readthedocs.io/en/latest/api.html#sshkey
    """
    sshkey = None
    path = Path(filename)
    basename = path.name
    if not path.exists():
        # print(f"No such key file {filename}")
        return None
    with path.open() as file:
        data = file.read()
        try:
            sshkey = asyncssh.import_private_key(data)
        except asyncssh.KeyImportError:
            while True:
                passphrase = getpass(
                    f"Enter passphrase for key {basename} : ")
                if not passphrase:
                    print(f"Ignoring key {filename}")
                    break
                try:
                    sshkey = asyncssh.import_private_key(data, passphrase)
                    break
                except asyncssh.KeyImportError:
                    print("Wrong passphrase")
        except Exception:                               # pylint: disable=w0703
            import traceback
            traceback.print_exc()
        return sshkey


def load_agent_keys(agent_path=None):
    """
    The ssh-agent is a convenience tool that aims at easying the use of
    private keys protected with a password. In a nutshell, the agent runs on
    your local computer, and you trust it enough to load one or several keys
    into the agent once and for good - and you provide the password
    at that time.

    Later on, each time an ssh connection needs to access a key,
    the agent can act as a proxy for you and pass the key along
    to the ssh client without the need for you to enter the password.

    The ``load_agent_keys`` function allows your python code to access
    the keys currently knwns to the agent. It is automatically called by the
    :class:`~apssh.nodes.SshNode` class if you do not explicit the set of
    keys that you plan to use.

    Parameters:
      agent_path: how to locate the agent;
        defaults to env. variable $SSH_AUTH_SOCK

    Returns:
      a list of SSHKey_ keys from the agent

    .. note::
      Use the command ``ssh-add -l`` to inspect the set of keys
      currently present in your agent.

    """
    # pylint: disable=c0111
    async def co_load_agent_keys(agent_path):
        # make sure to return an empty list when something goes wrong
        try:
            async with asyncssh.SSHAgentClient(agent_path) as agent_client:
                keys = await agent_client.get_keys()
                return keys
        except Exception as exc:                        # pylint: disable=w0703
            # not quite sure which exceptions to expect here
            print(f"When fetching agent keys: "
                  f"ignored exception {type(exc)} - {exc}")
            return []

    agent_path = agent_path or os.environ.get('SSH_AUTH_SOCK', None)
    if agent_path is None:
        return []
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(co_load_agent_keys(agent_path))


def load_private_keys(command_line_keys=None, verbose=False):
    """
    A utility that implements a default policy for locating
    private keys.

    Parameters:
      command_line_keys: a collection of local filenames that should contain
        private keys; this should correspond to keys that a user has
        explicitly decided to use through a command-line option or similar;
      verbose: gives more details on what is going on.

    This function is used both by the apssh binary, and by the
    :class:`~apssh.nodes.SshNode` class.
    Here's for example how `apssh` locates private keys:

    - 1. If no keys are given as the ``command_line_keys`` parameter
         (typically through the apssh `-k` command line option), then:

      - 1.a if an *ssh agent* can be reached using the `SSH_AUTH_SOCK`
          environment variable, and offers a non-empty list of keys,
          ``apssh`` will use the keys loaded in the agent

      - 1.b otherwise, `apssh` will use
         ``~/.ssh/id_rsa`` and ``~/.ssh/id_dsa`` if they exist

    - 2. If keys are specified on the command line

      - 2.c That exact list is used for loading private keys

    .. note::
      Use ``ssh-add`` for managing the keys known to the agent.

    """
    filenames = []
    if not command_line_keys:
        agent_keys = load_agent_keys()
        # agent has stuff : let's use it
        if agent_keys:
            if verbose:
                print(f"apssh has loaded {len(agent_keys)} keys from the ssh agent")
            return agent_keys
        else:
            if verbose:
                print(f"apssh has loaded no keys from agent")
        # use config to figure out what the default keys are
        filenames = default_private_keys
        if verbose:
            print(f"apssh will try to load {len(filenames)} default keys")
    else:
        filenames = command_line_keys
        if verbose:
            print(f"apssh will try to load {len(filenames)} keys from the command line")
    keys = [import_private_key(filename) for filename in filenames]
    valid_keys = [k for k in keys if k]
    if verbose:
        print(f"apssh has loaded {len(valid_keys)} keys")
    return valid_keys

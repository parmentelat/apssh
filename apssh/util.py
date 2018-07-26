"""
A set of helper functions for the apssh package
"""

import sys
import asyncio
import apssh

def print_stderr(*args, **kwds):
    """
    A shorthand for ``print()`` but on standard error
    """
    print(file=sys.stderr, *args, **kwds)

def close_ssh_from_sched(scheduler):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(co_close_ssh_from_sched(scheduler))

async def co_close_ssh_from_sched(scheduler):
    jobs = scheduler.jobs
    nodes = set()
    gateways = set()
    not_gateways = set()

    for job in jobs:
        if isinstance(job, apssh.SshJob)\
         and isinstance(job.node, apssh.SshProxy):
            nodes.add(job.node)
            if job.node:
                if job.node.gateway:
                    not_gateways.add(job.node)
                    gateways.add(job.node.gateway)
                else:
                    gateways.add(job.node)
    middle_nodes = set()
    killable_nodes = set()

    while len(not_gateways) > 0:
        for node in not_gateways:
            if node.gateway in not_gateways:
                middle_nodes.add(node.gateway)
        killable_nodes = not_gateways - middle_nodes
        middle_nodes = set()
        not_gateways = not_gateways - killable_nodes
        for node in killable_nodes:
            await node.close()
        killable_nodes = set()

    for node in gateways:
        await node.close()


def check_arg_type(instance, types, message):
    """
    The basic brick for explicit type checking in the apssh code

    raise ValueError if instance is not of any of the types

    types parameter is passed to isinstance, so may be either
    a class or a tuple of classes

    message would help identify the issue

    example:
      check_arg_type("foo.bar", SshProxy, "SshProxy.gateway")

    would result in a ValueError labelled with string

    >  SshProxy.gateway is expected to be an instance of SshProxy,
    >  got a str instead
    """
    if isinstance(instance, types):
        return

    # build a helpful error message

    # expected
    def atomic_typename(typeobj):                       # pylint: disable=c0111
        return typeobj.__name__
    if isinstance(types, tuple):
        msg_expected = " or ".join(atomic_typename(t) for t in types)
    else:
        msg_expected = atomic_typename(types)

    # received
    msg_received = atomic_typename(type(instance))

    # asembled
    msg_complete = "{} is expected to be an instance of {}, got a {} instead"\
                   .format(message, msg_expected, msg_received)
    raise ValueError(msg_complete)

# pylint: disable=

from collections import defaultdict

import asyncio

from .sshproxy import SshProxy
from .nodes import SshNode

def close_ssh_in_scheduler(scheduler):
    """
    Convenience: synchroneous version of :py:obj:`co_close_ssh_in_scheduler()`.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(co_close_ssh_in_scheduler(scheduler))

async def co_close_ssh_in_scheduler(scheduler, manage_gateways=True):
    """
    This utility function allows to close all ssh connections
    involved in a scheduler.

    Its logic is to find all `SshNode` instances referred in the jobs
    contained in the scheduler, nested schedulers included. All the attached
    ssh connections are then closed, starting with the remotest ones.

    Parameters:
      manage_gateways (bool): when this parameter is False, all the nodes that
        appear in at least one job are considered. If it is True,
        then in addition to that, all the nodes that appear as a gateway
        of a node in that first set are considered as well.
    """
    # gather all relevant instances of SshJob
    nodes_set = {
        job.node for job in scheduler.iterate_jobs()
        if isinstance(job.node, SshNode)
    }
    # transitive closure to gather gateways as well
    # can't modify the subject of a for loop
    gateways_set = set()
    if manage_gateways:
        def recursive_scan(node):
            gateway = node.gateway
            if gateway:
                gateways_set.add(gateway)
                recursive_scan(gateway)
        for node in nodes_set:
            recursive_scan(node)
        nodes_set |= gateways_set

    # gather nodes by distance
    dist_dict = defaultdict(list)
    for node in nodes_set:
        dist_dict[node.distance()].append(node)

    # sort them, remotest first
    distances = list(dist_dict.keys())
    distances.sort(reverse=True)

    for distance in distances:
        nodes = dist_dict[distance]
        close_tasks = [node.close() for node in nodes]
        await asyncio.gather(*close_tasks)

    # xxx what should this return ?
    return

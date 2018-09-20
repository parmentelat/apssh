# pylint: disable=c0111

import asyncio

from collections import defaultdict

from .sshjob import SshJob
from .nodes import SshNode


def _distances_dict(scheduler, manage_gateways):
    """
    Return a dictionary distance -> [nodes]
    """
    # gather all relevant instances of SshJob
    nodes_set = {
        job.node for job in scheduler.iterate_jobs()
        if isinstance(job, SshJob)
        and isinstance(job.node, SshNode)
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

    return dist_dict



def close_ssh_in_scheduler(scheduler, manage_gateways=True):
    """
    Convenience: synchroneous version of :py:obj:`co_close_ssh_in_scheduler()`.

    Parameters:
      manage_gateways (bool): passed as-is

    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(
        co_close_ssh_in_scheduler(scheduler, manage_gateways))


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

    # gather all nodes
    dist_dict = _distances_dict(scheduler, manage_gateways)

    # sort them, remotest first
    for distance in sorted(list(dist_dict.keys()), reverse=True):
        nodes = dist_dict[distance]
        close_tasks = [node.close() for node in nodes]
        await asyncio.gather(*close_tasks)

    # xxx what should this return ?
    return


############################## topologies / graphical output
def topology_dot(scheduler):
    """
    Computes the relationship between nodes and gateways,
    for a given scheduler.

    Returns:
      str: a string in DOT format.
    """
    dist_dict = _distances_dict(scheduler, manage_gateways=True)

    distances = sorted(list(dist_dict.keys()))
    indices = {}

    result = ''
    result += 'digraph apssh{\n'
    result += 'graph[];\n'
    result += '0 [style="rounded", label="Local Node", shape="box"]\n'
    index = 0
    for distance in distances:
        for node in dist_dict[distance]:
            index += 1
            indices[node] = index
            result += '{} [style="rounded", label="{}", shape="box"]\n'\
                      .format(index, node.__user_host__())
    for distance in distances:
        for node in dist_dict[distance]:
            upstream = 0 if not node.gateway else indices[node.gateway]
            result += '{} -> {}\n'.format(upstream, indices[node])
    result += '}\n'
    return result


def topology_graph(scheduler):
    """
    Much like ``Scheduler.graph()`` in ``asynciojobs``, this convenience
    function creates a graphviz graph object, that can be used to visualize the
    various nodes and gateways present in a scheduler, through the
    relationship: x *is used as a gateway to reach* y



    Returns:
      graphviz.Digraph: a graph

    This method is typically useful in a Jupyter notebook,
    so as to visualize a topology in graph format - see
    http://graphviz.readthedocs.io/en/stable/manual.html#jupyter-notebooks
    for how this works.

    The dependency from ``apssh`` to ``graphviz`` is limited
    to this function, and :py:obj:`~apssh.topology.topology_as_pngfile`
    as these are the only places that need that library,
    and as installing ``graphviz`` can be cumbersome.

    For example, on MacOS I had to do both::

      brew install graphviz     # for the C/C++ binary stuff
      pip3 install graphviz     # for the python bindings
    """

    from graphviz import Source
    return Source(source=topology_dot(scheduler))


def topology_as_dotfile(scheduler, filename):
    """
    Convenience function to store a dot file from a schedulerself.

    Parameters:
      scheduler:
      filename: output filename
    """
    with open(filename, 'w') as output:
        output.write(topology_dot(scheduler))
    return "(Over)wrote {}".format(filename)


def topology_as_pngfile(scheduler, filename):
    """
    Convenience wrapper that creates a png file.

    Parameters:
      scheduler:
      filename: output filename, without the ``.png`` extension
    Returns:
      created file name

    Notes:
      - This actually uses the binary `dot` program.
      - A file named as the output but with a ``.dot`` extension
        is created as an artefact by this method.
    """
    # we refrain from using graph.format / graph.render
    # because with that method we cannot control the location
    # of the .dot file; that is dangerous when using e.g.
    #    scheduler.export_as_pngfile(__file__)
    import os
    dotfile = "{}.dot".format(filename)
    pngfile = "{}.png".format(filename)
    topology_as_dotfile(scheduler, dotfile)
    os.system("dot -Tpng {} -o {}"
              .format(dotfile, pngfile))
    return pngfile

from job import Job
from engine import Engine

from sshjobs import SshProxy, SshJob, SshJobScript
from apssh.formatters import ColonFormatter

async def aprint(*args, **kwds):
    print(*args, **kwds)

bash_script = "sshtests1.sh"
with open(bash_script) as f:
    bash_oneliner = f.read()

####################
def two_passes(synchro, debug=False):

    """
    synchro = True : wait for pass1 to complete on all nodes before triggering pass2
    synchro = False: run pass2 on node X as soon as pass1 is done on node X
    """
    
    msg = "synchro={}".format(synchro)

    # nodes to use
    node_ids = range(1, 4)

    nodes = [ "fit{:02d}".format(id) for id in node_ids ]
    proxies = [ SshProxy(hostname=node, username="root",
                         formatter=ColonFormatter(),
                         debug=debug,
                     )
                for node in nodes ]

    print(40*'*', msg)
    command = "/bin/bash -c '{}'".format(bash_oneliner)
    jobs1 = [ SshJob(proxy=proxy,
                     command=command,
                     label="{} - pass1 on {}".format(msg, node))
              for (proxy, node) in zip(proxies, nodes)]
    

    middle = Job(aprint( 20*'=' + 'middle'), label='middle')

    jobs2 = [ SshJobScript(proxy=proxy,
                           local_script=bash_script,
                           label="{} - pass2 on {}".format(msg, node))
              for (proxy, node) in zip(proxies, nodes)]
    
    for j1 in jobs1:
        middle.requires(j1)

    if not synchro:
        for j1, j2 in zip(jobs1, jobs2):
            j2.requires(j1)
    else:
        for j2 in jobs2:
            j2.requires(middle)

    e = Engine(*(jobs1+[middle]+jobs2), debug=debug)
    orch = e.orchestrate()
    print('********** orchestrate ->', orch)
    e.list()
    print('**********')

if __name__ == '__main__':

    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-d", "--debug", action='store_true')
    # -1 : first test
    # -2 : second test
    # -3 : both
    parser.add_argument("-p", "--passes", type=int, default=3)
    args = parser.parse_args()
    debug = args.debug
    passes = args.passes

    if passes & 1:
        two_passes(True, debug)
    if passes & 2:
        two_passes(False, debug)
    

from job import Job
from engine import Engine

from sshjobs import SshProxy, SshJob, SshJobScript
from apssh.formatters import ColonFormatter

async def aprint(*args, **kwds):
    print(*args, **kwds)

# first script does not take args as it it passed directly as a command
with open("sshtests1.sh") as f:
    bash_oneliner = f.read()

# this one accepts one message argument
bash_script = "sshtests2.sh"

####################
def two_passes(synchro, debug=False, skip1=False, skip2=False):

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
    jobs1 = [ SshJob(proxy=proxy,
                     command = [ "/bin/bash -c '{}'".format(bash_oneliner)],
                     label="{} - pass1 on {}".format(msg, node),
    )
              for (proxy, node) in zip(proxies, nodes) ]
    

    middle = Job(aprint( 20*'=' + 'middle'), label='middle')

    jobs2 = [ SshJobScript(proxy=proxy,
                           command = [bash_script, 'pass2'],
                           label="{} - pass2 on {}".format(msg, node),
                       )
              for (proxy, node) in zip(proxies, nodes)]
    
    for j1 in jobs1:
        middle.requires(j1)

    if not synchro:
        for j1, j2 in zip(jobs1, jobs2):
            j2.requires(j1)
    else:
        for j2 in jobs2:
            j2.requires(middle)

    e = Engine(debug=debug)
    if not skip1:
        e.update(jobs1)
    e.add(middle)
    if not skip2:
        e.update(jobs2)
    print("========== sanitize")
    e.sanitize()
    print("========== rain check")
    e.rain_check()
    print("========== orchestrating")
    orch = e.orchestrate()
    print('********** orchestrate ->', orch)
    e.list()
    print('**********')

if __name__ == '__main__':

    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-d", "--debug", action='store_true')
    parser.add_argument("--skip1", action='store_true')
    parser.add_argument("--skip2", action='store_true')
    # -1 : first test
    # -2 : second test
    # -3 : both
    parser.add_argument("-p", "--passes", type=int, default=3)
    args = parser.parse_args()
    debug = args.debug
    skip1 = args.skip1
    skip2 = args.skip2
    passes = args.passes

    if passes & 1:
        two_passes(True, debug, skip1, skip2)
    if passes & 2:
        two_passes(False, debug, skip1, skip2)
    

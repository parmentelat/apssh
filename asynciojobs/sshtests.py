import os.path

from asynciojobs.engine import Engine
from asynciojobs.job import Job
from asynciojobs.sshjobs import SshProxy, SshJob, SshJobScript

from apssh.formatters import ColonFormatter

async def aprint(*args, **kwds):
    print(*args, **kwds)

# first script does not take args as it it passed directly as a command
path = "asynciojobs"
with open(os.path.join(path, "sshtests1.sh")) as f:
    bash_oneliner = f.read()

# this one accepts one message argument
bash_script = os.path.join(path, "sshtests2.sh")

####################
def two_passes(node_ids, synchro, debug=False, before=True, after=True):

    """
    synchro = True : wait for pass1 to complete on all nodes before triggering pass2
    synchro = False: run pass2 on node X as soon as pass1 is done on node X
    """
    
    msg = "synchro={}".format(synchro)

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
    if before:
        e.update(jobs1)
    e.add(middle)
    if after:
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
    parser.add_argument("--after", action='store_true')
    parser.add_argument("--before", action='store_true')
    # -1 : first test
    # -2 : second test
    # -3 : both
    parser.add_argument("-s", "--scenarii", type=int, default=3)
    parser.add_argument("node_ids", nargs="*", type=int, default=[1,2,3])

    args = parser.parse_args()
    debug = args.debug
    scenarii = args.scenarii
    node_ids = args.node_ids

    # --after means only after
    if args.before:
        before, after = True, False
    elif args.after:
        before, after = False, True
    else:
        before, after = True, True
    if scenarii & 1:
        two_passes(node_ids, True, debug, before, after)
    if scenarii & 2:
        two_passes(node_ids, False, debug, before, after)
    

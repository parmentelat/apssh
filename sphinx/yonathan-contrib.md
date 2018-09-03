# branches

Voici la liste des branche sur les différents modules :

### asynciojobs:

* ~~ittrate-job~~ :  **in 0.12.11**

  ~~Contient le patch qui permet à APSSH de récupérer les jobs à l’intérieur de scheduler nestés. Attention pour une obscure raison, je l’ai basé sur une version contenant le patch de implicit-shutdown.~~

* implicit-shutdown : **reste à intégrer**

  Réactive le shutdown implicite à la fin d’un scheduler, un timeout ou une exception.

* ~~implicit_shutdown : Deprecated & removed was 92e7425~~

### apssh :

* close-con :

  Contient un patch qui permet de fermer correctement les connections ssh sur les noeuds et leur gateway. A utiliser avec la branche iterate-job de asynciojobs. Contient également les tests sur les connections et leur utilitaires.

* prezombie-kill :

  Contient le patch qui permet la synchronisation de services à l’intérieur des schedulers. Le patch qu’il faudra utiliser quand ‘Openssh' aura implémenté la section 6.9 de la RFC s’y trouve également. Il y a aussi les tests portant sur  cette feature.

* signal-exit :

  Contient un patch qui permet de white-list des signal/exit-code spécifiques sur un job critique. Contient aussi une amélioration du retour d’une commande. Il y a aussi les tests portant sur la feature.


* ~~Service_Killing~~ :  deleted - was on commit 86707a7b9ec5e355330db2c3a6f9bb0d3d6b2c02

  ~~Dedans on y trouve à la fois un patch pour tuer les processes de type
  “service” et un patch pour fermer les connections. Son contenu a donc été
  scindé dans d’autres branches (y compris la partie de la branche master).~~

### r2lab-python:

* header-exp :

  Contient une série de méthodes dans r2lab/utils.py qui permettent de définir un scheduler gérant le check leases et les images afin de commencer une expérience.

******

# Howto use new features

### apssh / prezombie kill :

Allow the famous client-server synchronisation, ie:

```python3
netcat_server_job = SshJob(
    node = server,
    forever = True,
    label = "nc serv",
    # service=True indicates that this command will be killed when its scheduler end
    command = Run("nc -l -k -p 12345", service=True)

    )

netcat_client_job = SshJob(
    node = LocalNode(),
    command = Run(f"sleep 4; cat test.txt | netcat -c {server_ip} 1234 ")

)

jobs = [netcat_client_job, netcat_server_job]
filesend = Scheduler(*jobs,
                    scheduler=scheduler,
                    critical = True,
                    verbose=verbose_ssh,
                    label="serv/cli relation")
```

### apssh / close-conn :

New way to close all connection. As of asynciojobs 11.1 we need to do it manually :

```python3
from apssh import util

[...]

ok = main_sheduler.orchestrate()
if ok:
  util.close_ssh_in_scheduler(main_scheduler)
```

## signal-exit :
Allow white-listing of exits code.

```python3
job = SshJob(node=node, forever=True,
             command=Run(f"sleep {wait_time*15}",
                         allowed_exits=["TERM"])
            )
```

New way to display exit code :
```DONE: 1   ☉ ☓   <SshJob `should fail`> [[ -> [1, 0]]]
```
Comes from :
```SshJob(node=self.gateway(),
             critical=False,
             commands=[Run("false"),
                       Run("true")],
             label="should fail")
```

### r2lab-python / header-exp :

Friendly function to check lease and turn-on/load image on the nodes.

```python3
import r2lab

from asynciojobs import Scheduler

sched = Scheduler()
#"" and None will load the default image.
dic_node_image = {"1": "gnuradio_batman",
                  "fit5": "",
                  "09": "",
                  "10":None,
                  "14":"",
                 }

list_sdr_on = [2, 5, 10, 15, 30, 37]
header_job = r2lab.generate_experiment_header(
    slicename="inria_batman",
    dic_node_image=dic_node_image,
    list_sdr_on=list_sdr_on)

sched.add(header_job)
```

# tests

## test_processes

Test on the combination of factor :
* Remote/Local,
* the job use Run/RunString/RunScript objects,
* the scheduler finish normally/with an exception/with a timeout,
* the job is/isn't in a nested scheduler,

there is one job per nested scheduler or one nested scheduler for all jobs.

Sometimes there is an exception that is thrown but it is not harmful for the test.

These exception come from the way we end the sleep command. By sending it a SIGTERM, it returns an
'exit on signal' exit code. With the patch on the branch signal-exit we could put the attribute
'allowed_exits=["TERM"]' in the Run() object to avoid this exception.

## test_connections :

There is 3 basic cases :
* Jobs using 1-hop ssh connections
* Jobs using 2-hop ssh connections
* Jobs using n-hop (more than 2) ssh connections

For the first type, we test when :

  * there is 4 commands on the same node
  * there is 1 command on 4 different nodes
  * there is 4 commands on each of the 4 different nodes

The second type contain the tests where there is :
  * 2 commands on 1 node that use 1 gateway
  * 1 commands on 2 nodes using the same gateway
  * 1 command running on 1 nodes for 2 different gateways
  * 2 commands for 2 nodes using the same gateway for 2 different gateways

Concerning the types of scheduler used for these 2 types of tests :
  * We use classic scheduler (aka non-nested)
  * We use nested scheduler with 1 job per schedulers
  * We use 1 job per nested scheduler inside another nested scheduler
  * We pack jobs by 2 inside 1 nested scheduler
  * We pack jobs by 2 inside a nested scheduler inside another nested scheduler

Each of these type of tests are done by either :
  * Calling the .close method directly on the nodes
  * Calling the `apssh.util.close_ssh_in_scheduler()` on the master scheduler

The third type of test consist only in building a hierarchy of nodes executing each a job :

```
gateway0 : echo hop0-0
   |
   --------> gateway1: echo hop1-0
                |
                --------> gateway2: echo hop2-0
                              |
                              --------> gateway3: echo hop3-0
```

And the close all the connection using the `apssh.util.close_ssh_in_scheduler()`.

***
As a side note : for this test we do not test the node.close method because we
are using asyncio and we have no way to guarantee that the hierarchy will
completely close from bottom to top. Moreover, it would not be very relevant
since we already test it for all the other cases.

In order to do all these tests, we use multiple methods to avoid to duplicate a lot of code:

* one

`def close_nodes(self, nodes, gateway_first=True)`:

Will close connection directly on given nodes.

The gateway_first argument indicates if the gateways are first in the nodes list.

* two

`def close_sched(self, sched, dummy_bool=False)`:

Will close the connection using 'apssh.util.close_ssh_in_scheduler()'
on the given scheduler. The dummy_bool argument is a nasty hack so that the method has the same
signature as the close_nodes method.

* three

`def populate_sched(self, scheduler, jobs, nested=0, pack_job=1)`:

Will populate the given scheduler with the given jobs using a way describe with the nested and pack_job arguments.
nested define the degree of nesting scheduler (0 is no nesting, 1 is 1 nested, 2 is one nested in on nested scheduler, etc)

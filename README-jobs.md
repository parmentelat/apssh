# Intro - what is `nepi-ng` ?

As much as `apssh` comes with a standalone binary that sysadmins might find useful for their routine jobs, an alternative usage of `apssh` is to create **`SshJob`** objects in conjunction with an `asyncio`'s **`Engine`** for **orchestrating** them.

Originally, the idea presented here addresses the needs of experimental research, where an experiment often boils down to running jobs like preparing a set of nodes, initializing them, running some bash script, collecting results, all of them having temporal relationships.

At least temporarily, we will refer to this approach as **`nepi-ng`**, `nepi` being an old-school standalone tool that we used to use for this kind of usages in the past.

# `apssh` and `asynciojobs`

## `asynciojobs`
`asynciojobs` is a microscopic orchestration engine for asyncio-based jobs - [see this link for details](https://github.com/parmentelat/asynciojobs/blob/master/README.ipynb). This is the part that handles the temporal relationships.

## `apssh.SshJob`

`apssh` ships with a few classes that allow you to write jobs in the `asynciojobs`  sense, that will actually run on ssh. 

At this early stage, these classes for now are limited to

* `SshNode` : describe how to reach a node (possible through a gateway)
* `SshJob` : to run one or several remote commands; each of these can be
  * `Run` : that is designed to run a command readily available on the target node
  * `RunScript` : when you have a local script file to run remotely, so there is a need to push it over there prior to running it
  * `RunString` : same idea, but you do not even have a local file, it's just a python string in memory; useful to embed your shell code inside a python code
* `SshJobCollector` and `SshJobPusher` : to transfer files back and forth

As the names may suggest:

* `SshJob`, `SshJobCollector` and `SshJobPusher` are suitable to run as `asynciojobs's` jobs, i.e. inside an engine.
* instances of each of these 3 classes must be created attached to a `SshNode` instance, that contains the details of the target node (hostname, username, gateway if relevant, etc...)
* An `SshJob` instance can contain a list of actual commands to run, of either of the 3 supported types, i.e. `Run`, `RunScript` or `RunString`

## example

You can see a very simple example of that idea implemented in 2 files

* [the python code](https://github.com/parmentelat/r2lab/blob/master/demos/jobs-angle-measure/angle-measure.py)
* and [the related shell script](https://github.com/parmentelat/r2lab/blob/master/demos/jobs-angle-measure/angle-measure.sh)
* plus, a summary of the objects involved [is depicted in this figure](https://github.com/parmentelat/r2lab/blob/master/demos/jobs-angle-measure/jobs.png)

## plain `nepi` equivalent

* You can find [the exact same experiment written in plain `nepi`](https://github.com/parmentelat/r2lab/blob/master/demos/nepi-angle-measure/angle-measure.py). 
* As can be seen, the paradigms are very similar for the programmer.

#### Where is `nepi` better ?
* It must be outlined however that `nepi-ng` at this point has a much smaller coverage as `nepi`'s, at it is restricted to `ssh`-based accesses - as opposed to `nepi` whose ambition was to cover a wide range of technos for controlling nodes, including specifics for `ns3`, XMPP-based `OMF` messaging system, `SFA` layer for provisioning, and so on ...
* Note however that `ssh`-based access is what we used to offer with PlanetLab, and what we offer now at R2lab - , so as long as this is your focus you're in the clear with `nepi-ng`.

#### Where is `nepi-ng` better ?
* All this being said, the `nepi-ng` version runs several orders of magnitude faster, essentially because 
  * it ensures that exactly one single ssh connection gets created to each node involved
  * no remote job is run in the background, so we know instantly when a job is finished - no need to cyclically check for processes remotely
  * and all stdout/stderr is redirected on the fly, so no need to retrieve this sort of data later on.

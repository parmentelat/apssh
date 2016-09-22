# Intro - what is `nepi-ng` ?

As much as `apssh` comes with a standalone binary that sysadmins might find useful for their routine jobs, an alternative usage of `apssh` is to create **`SshJob`** objects in conjunction with an `asyncio`'s **`Engine`** for **orchestrating** them.

Originally, the idea presented here addresses the needs of experimental research, where an experience often boils down to running jobs like preparing a set of nodes, initializing them, running some bash script, collecting results, all of them having temporal relationships.

At least temporarily, we will refer to this approach as **`nepi-ng`**, `nepi` being a standalone tool that we used to use for this kind of usages in the past.

# `apssh` and `asynciojobs`

## `asynciojobs`
`asynciojobs` is a microscopic orchestration engine for asyncio-based jobs - [see this link for details](https://github.com/parmentelat/asynciojobs/blob/master/README.ipynb). This is the part that handles the temporal relationships.

## `apss.sshjobs.SshJob`

`apssh` ships with a few classes that allow you to write jobs in the `asynciojobs`  sense, that will actually run on ssh. 

At this early stage, these classes for now are limited to

* `SshNode` : describe how to reach a node (possible through a gateway)
* `SshJob` : to run a remote command
* `SshJobScript` : to push a local script remotely and run it
* `SshJobCollector` : to retrieve one or several files

## example

You can see a very simple example of that idea implemented in 2 files

* [the python code](https://github.com/parmentelat/r2lab/blob/master/demos/jobs-angle-measure/angle-measure.py)
* and [the related shell script](https://github.com/parmentelat/r2lab/blob/master/demos/jobs-angle-measure/angle-measure.sh)
* plus, a summary of the objects involved [is depicted in this figure](https://github.com/parmentelat/r2lab/blob/master/demos/jobs-angle-measure/jobs.png)

## plain `nepi` equivalent

* You can find [the exact same experiment written in plain `nepi`](https://github.com/parmentelat/r2lab/blob/master/demos/nepi-angle-measure/angle-measure.py). 
* As can be seen, the paradigms are very similar.
* It must be outlined however that `nepi-ng` at this point has a much lower coverage as `nepi`'s, at it focuses on `ssh`-based accesses.
* All this being said, the `nepi-ng` version runs several orders of magnitude faster, essentially because it ensures exactly one single ssh connection gets created to each node involved.
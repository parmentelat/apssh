# `apssh` and `asynciojobs`

Originally, the idea presented here addresses the needs of experimetal research, where an experience often boils down to running jobs like preparing a set of nodes, initializing them, running some bash script, collecting results, all of them having temporal relationships.

## `asynciojobs`
`asynciojobs` is a microscopic orchestration engine for asyncio-based jobs - [see this link for details](https://github.com/parmentelat/asynciojobs/blob/master/README.ipynb). This is the part that handles the temporal relationships.

## `apss.sshjobs.SshJob`

`apssh` ships with a few classes that allow you to write jobs in the `asynciojobs`  sense, that will actually run on ssh. 

At this early stage, these classes for now are limited to

* `SshNode` : describe how to reach a node (possible through a gateway)
* `SshJob` : to run a remote command
* `SshJobScript` : to push a local script remotely and run it

## Example

You can see a very simple example of that idea implemented in 2 files

* [the python code](https://github.com/parmentelat/r2lab/blob/master/demos/jobs-angle-measure/angle-measure.py)
* and [the related shell script](https://github.com/parmentelat/r2lab/blob/master/demos/jobs-angle-measure/angle-measure.sh)
* a summary of the objects involved [is depicted in this figure](https://github.com/parmentelat/r2lab/blob/master/demos/jobs-angle-measure/jobs.png)
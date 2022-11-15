# `apssh` - asynchronous parallel ssh

## what's included ?

This tool leverages the Python asynchronous paradigm and comes with

* a standalone `apssh` command for running remote commands on a bunch of hosts
  in parallel, as well as the `appull` and `appush` commands to perform parallel
  copies, that sysadmins might find useful for their routine jobs,
* an API with which one can create **`SshJob`** objects
  in conjunction with an `asynciojob`'s **`Scheduler`** for
  **orchestrating** them.

Please refer to <http://apssh.readthedocs.io/> for a complete documentation bundle.

## what is `nepi-ng` ?

Originally, the idea presented here addresses the needs of experimental
research, where an experiment often boils down to running jobs like preparing a
set of nodes, initializing them, running some bash script, collecting results,
all of them having temporal relationships.

To that end, the 2 libraries `asynciojobs` and `apssh` complement each other
to offer a powerful programing environment that we have branded `nepi-ng`; its 2 parts are thus:

## `asynciojobs`
`asynciojobs` is a microscopic orchestration scheduler for asyncio-based jobs -
[see this link for
details](https://github.com/parmentelat/asynciojobs/blob/master/README.md).
This is the part that handles the temporal relationships.

## `apssh`

`apssh` ships with a few classes that allow you to write jobs in the
`asynciojobs`  sense, that will actually run on ssh:

* `SshNode` : describe how to reach a node (possible through a gateway)
* `SshJob` : to run one or several remote commands; each of these can be
  * `Run` : that is designed to run a command readily available on the target
    node
  * `RunScript` : when you have a local script file to run remotely, so there is
    a need to push it over there prior to running it
  * `RunString` : same idea, but you do not even have a local file, it's just a
    python string in memory; useful to embed your shell code inside a python
    code
  * `Pull` or `Push` for file transfers over SFTP

As the names may suggest:

* an `SshNode` instance contains the details of the target node (hostname,
  username, gateway if relevant, etc...), and it can be thought of as an ssh
  connection;
* `SshJob`, is suitable to run as `asynciojobs's` jobs, i.e. inside a scheduler;
* an `SshJob` instance contains a list of the actual commands to run, that can
  be a mix of remote executions and file transfers.

## examples

You can see a very simple example of that idea implemented in 2 files

* [the python code](https://github.com/fit-r2lab/r2lab-demos/blob/master/orion/angle-measure.py)
* and [the related shell script](https://github.com/fit-r2lab/r2lab-demos/blob/master/orion/angle-measure.sh)
* plus, a summary of the objects involved [is depicted in this
  figure](https://github.com/fit-r2lab/r2lab-demos/blob/master/orion/jobs.png)

Another, simpler example, illustrates how to take advantage of the YAML loader, see

* [the `my-first-nepi-ng-script` folder in
  <https://github.com/fit-r2lab/demos](https://github.com/fit-r2lab/r2lab-demos/tree/master/my-first-nepi-ng-script)
* and in particular the 2 versions named `demo-v1.py` and `demo-v2.py` that
  implement the exact same behaviour but that use
  * a pure Python approach (v1)
  * the YAML loader (v2)

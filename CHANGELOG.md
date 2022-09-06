# ChangeLog

## 0.19.1 - 2022 Sep 6

* no change, but a dusted off doc & test environment
* the code has no change but since we depend on asynciojobs
  it is safe to assume that we depend on python-3.9

## 0.19.0 - 2022 Mar 20

* turn off loading of OpenSSH-compatible config files that
  is more harmful than helpful

## 0.18.3 - 2021 Feb 3

* new option Run(ignore_outputs=True) useful on local nodes
  where Service cannot safely used to run background processes

## 0.18.2 - 2021 Feb 3

* revised, and tested, implementation of Service(environ=)

## 0.18.1 - 2021 Feb 3

* hot bugfix

## 0.18.0 - 2021 Feb 2

* add support for deferred evaluation, i.e. the creation of Run-like and Service
  instances based on strings that are not yet fully known at scheduler-creation time
* 3 new classes are defined to that end: Variables, Deferred and Capture

## 0.17.6 - 2020 Nov 27

* robustified loading keys from agent
* adaptation to changes in asyncssh regarding the initialization of SSHAgentClient
* as a consequence our load_agent_keys() function no longer accepts a loop argument
* 0.17.5 was BROKEN

## 0.17.4 - 2020 May 20

* no change in code
* reviewed recipe for uploading to PyPI
* long_description now based on proper README in markdown

## 0.17.3 - 2018 Dec 19

* Service class continued:
* parameter reset_failed renamed into stop_if_running
* more robust wrt restarting the same service
* 0.17.2 was fine but used a couple f-strings which broke readthedocs

## 0.17.1 - 2018 Dec 13

* Service class revisited:
* parameter service_id is mandatory
* comes with an implicit reset-failed by default
* no longer salted
* 0.17.0 was breaking compatibility for no benefit, please don't use

## 0.16.0 - 2018 Nov 26

* new option -K / --ok-if-no-key - don't check for at least one key
* micro-change in labelling nodes in a graph: swap space and colon

## 0.15.1 - 2018 Oct 11

* the Service class accepts a new `environ` attribute that lets user define e.g.
  USER or HOME similar environment variables
* 0.15.0 was broken

## 0.14.2 - 2018 Oct 10

* minor cosmetic tweaks
  * graphical output shows job number for easier binding to textual listing
  * default RunString textual repr is based on a truncated script body

## 0.14.1 - 2018 Sep 20

* bugfix: computation of distances was broken with jobs that were not sshjob instances
* bugfix: creation of a Service instance with no service_id was broken

## 0.14.0 - 2018 Sep 4

* new class `Service`: simplify creation of things running in the background,
  like tcpdump and other similar activities that need to be started and stopped;
  this feature leverages `systemd-run`

## 0.13.2 - 2018 Sep 3

* a tool to produce a graphical representation of the
  "node x is the gateway for node y" relationship. See `topology_as_dot` or `topology_as_graph`.
* 0.13.1 used lingering f-strings

## 0.13.0 - 2018 Sep 3

* command objects can define a `allowed_exits` attribute; this allows
  for instance to state that a command may be killed,
  or return a non-zero retcod, while still being deemd OK.
* `apssh.close_ssh_in_scheduler` now allows to explicitly close all ssh
  connections invlolved in a scheduler; coroutine `co_close_ssh_in_scheduler` available as well;
* more cleanly close connection to ssh agent when fetching keys
* ssh sessions now retain exit code or signal, when relevant
* `SshJob.repr()` gives more details on which command failed and how,
  resulting in a more troubleshooting-friendly listing for apssh schedulers,
  especially with multi-command jobs.
* much wider test scope, redesigned to work exclusively in standalone mode,
  using a local ubuntu virtualbox.


## 0.12.1 - 2018 May 22

* bugfix, selection between RunScript and RunString in apssh -s
* optimize lazy connections, don't wait for the lock if connection is up
* tweaked tests to use non-critical schedulers when it matters;
  this is for asynciojobs 0.11

## 0.11.3 - 2018 May 4

* inside an SshJob, a command that has an empty label won't show up at all,
  not even as an empty line

## 0.11.2 - 2018 May 4

* bugfix, failing SshJob tried to throw an exception using the command()
  method on the failing command, which is no longer available

## 0.11.1 - 2018 Apr 30

* adaptation for asynciojobs v0.10: `jobs_window` now is a scheduler attribute
  and not a parameter to run()

## 0.10.3 - 2018 Apr 18

* still cleaner and more complete doc
  * in particular doc now covers formatters thoroughly
* new exception class CommandFailedError

## 0.10.2 - 2018 Apr 17

* apssh binary was broken, searching for config files in ~/.apssh/ was not working

## 0.10.1 - 2018 Apr 17

* in line with asynciojobs 0.7 labelling system
* command objects can have a label set on them
  to shorten the graphical view
* major overhaul on the documentation
  * using the numpy style in docstrings
* code is now totally pep8/flake8- and pylint- clean

## 0.9.4 - 2018 Mar 28

* revisited graphical rendering of RunString
* pylint'ed
* code layout changed, SshNode and LocalNode in nodes.py

## 0.9.3 - 2018 Mar 13

* *Warning*: a disruptive change in the constructor for SshProxy/SshNode
  has been introduced; from now on, all parameters but the hostname are keyword-only parameters
* the underlying asyncssh is now expected to support *x11_forwarding*,
  there no longer is a fallback if not
* adopted new doc loayout with no source/ subdir in sphinx/


## 0.9.2 - 2018 Feb 25

* SshProxy/SshNode have a modified signature
  * single parameter hostname
  * all the rest are now keyword-only parameters
  * warning, this might break some scripts
* doc uses new sphinx theme

## 0.9.1 - 2018 Feb 9

* Improved policy when using SshNode with no provided keys:
  will first look for agent keys, and then if there is none,
  will look for private keys, prompting for passwords if found

## 0.8.1 - 2018 Jan 26

* bugfix - missing import os

## 0.8.0 - 2018 Jan 23

* replaced use of os.path with pathlib.Path
* minor fixes

## 0.7.7 - 2018 Jan 16

* defined dot_label() for nicer png graphs

## 0.7.6 - 2018 Jan 16

* a second attempt to fix bogus pip install

## 0.7.5 - 2018 Jan 16

* an attempt to fix bogus pip install

## 0.7.4 - 2018 Jan 14

* decidedly these type checks were botched

## 0.7.3 - 2018 Jan 11

* implement #6 about showing local subprocesses (LocalNode)
  stdout and stderr on the fly

## 0.7.2 - 2018 Jan 11

* bugfix - type checks were too stringent on LocalNode

## 0.7.1 - 2017 Dec 19

* add argument checking for the node part of a SshJob

## 0.7.0 - 2017 Dec 19

* add type verifications when building a SshProxy instance
* new policy to locate defaut private keys: if no key can be found
  at the ssh agent, then ~/.ssh/id_rsa and ~/.ssh/id_dsa are
  used.

## 0.6.3 - 2017 Nov 2

* bugfix

## 0.6.0 - 2017 Nov 2

* can create SshJob with keep_connection=True
* check a node object is an instance of SshProxy
* more robust load_agent_keys - return [] if cannot reach
* SshJob - change logic of failed commands - exception only raised if critical

## 0.5.6 - 2016 Dec 15

* bugfix - RunScript and details()

## 0.5.5 - 2016 Dec 12

* protect os.getlogin()

## 0.5.4 - 2016 Dec 8

* warning about asyncssh and 1.7.3 to appear only when actually using x11
* 0.5.3 had that still wrong

## 0.5.2 - 2016 Dec 8

* better feedback for connecting/disconnections
  * write error messages on stderr for serious errors
    even if not verbose
  * show username in most cases
* add support for x11 forwarding with Run(x11=True)
  * also available on RunString and RunScript
  * requires apssh > 1.7.3, which is not yet out though
* bugfix: both RunScript and RunString add a random part
  at the end of remote command name - to allow for multiple
  simulataneous runs
* use proper SshJob's instead of individual Run commands
* use setuptools instead of disutils

## 0.5.1 - 2016 Dec 5

* windowing now performed with asynciojobs
* -u/--user is now -l/--login like in vanilla `ssh`

## 0.4.8 - 2016 Dec 5

* Do not automatically add any quotes to commands run remotely
  with Run{String,Script}, this is the caller's responsability

## 0.4.7 - 2016 Dec 5

* LocalNode.username is defined - used in details

## 0.4.6 - 2016 Dec 2

* it is possible to set `verbose` when creating a `SshJob` object
* in this case, this value is used to set/override `verbose` in
  all the `commands` that are part of that `SshJob`
* 0.4.5 is broken (commands verbosity is always on)

## 0.4.4 - 2016 Nov 30

* welcome to the LocalNode class for running local commands
* big room for improvements, but at least we get a decent way
  to write the C1 tutorial in r2lab
* 0.4.3 is broken

## 0.4.2 - 2016 Nov 30

* comes with a sphinx documentation ready to publish on
  nepi-ng.inria.fr/apssh

## 0.4.1 - 2016 Nov 26

* add verbose flag to SshProxy/SshNode
  useful to see when a connection fails
* add verbose flag to Run* classes
  useful to see commands details when running remotely

## 0.4.0 - 2016 Nov 21

* align on asynciojobs 0.4.0
* that is to say, rename engine into scheduler

## 0.3.1 - 2016 Nov 18

* Redesigned interface
* a single AbstrctJob class SshJob
* is created with a list of AbstractCommands
* that can be any of `Run`, `RunScript`, `RunString`, `Push` or `Pull`
* so now script scenarii can embed their shell fragments inside a python script
* also this is in accordance with asynciojobs 0.3.3 for
  the details() and default_label() protocols

## 0.2.17 - 2016 Oct 28

* CaptureFormatter allows to capture the output of a command

## 0.2.16 - 2016 Oct 28

* bugfix - protect against issues when closing connection

## 0.2.15 - 2016 Oct 4

* connect_put_run propagates follow_symlinks, which defaults to True

## 0.2.14 - 2016 Oct 4

* minor fixes

## 0.2.13 - 2016 Oct 4

* SshJobScript accepts command= or commands= just like SshJob
* apssh -i become -k
* apssh -i now is for included files when running -s
* 0.2.11 and 0.2.12 are broken

## 0.2.10 - 2016 Oct 4

* SshJobScript has optional includes that get pushed too
* SshProxy/SshNode : renamed client_keys into just keys
* SshNode with no keys: default now is to use ssh agent keys

## 0.2.9 - 2016 Sep 30

* SshJobScript fails if script retcod is not 0

## 0.2.8 - 2016 Sep 27

* for --target, files and directories are also searched in ~/.apssh

## 0.2.7 - 2016 Sep 27

* new class SshJobPusher
* SshJob(commands=..) allows to run several commands in a row
* all SshJob* classes are critical by default

## 0.2.6 - 2016 Sep 22

* class `SshJobCollector` can retrieve data

## 0.2.5 - 2016 Sep 22

* formatter cleanupmostly done
* all verbose reporting about connections and authentication and the like
  is now primarily done throuch asyncssh callbacks, except for sessions and sftp

## 0.2.4 - 2016 Sep 21

* big cleanup in formatters that can be verbose or not
* sshjobs uniformly refers to *node* rather than *proxy* including in attributes

## 0.2.3 - 2016 Sep 20

* exception handling :
  * more uniform way to write jobs, always let exceptions through
  * ending up in simpler code

## 0.2.2 - 2016 Sep 19

* add mutual exclusion locks to SshProxy connection and disconnection
  to ensure that an object gets connected only once

## 0.2.1 - 2016 Sep 19

* support for -g / --gateway option for 2-hops connections
* support for getting keys at the ssh agent if can be located
* tentatively fixes issue #2

## 0.1.1 - 2016 Sep 15

* add missing apssh.jobs to pypi packaging

## 0.1.0 - 2016 Sep 15

* fixes issue #1
* fixes SFTP closing
* addition of SshJobs to be used with asynciojobs

## 0.0.8 - 2016 Sep 8

* script mode still runs in remote home directory, does not cd in .apssh

## 0.0.7 - 2016 Sep 7

* `--target` and `--exclude` can be used with a directory

  This is useful in combination with `--mark`, so that the second run can easily focus on successful nodes

```
# first pass to determine nodes that are responding
apssh -o pass1 --mark -t MYNODES hostname
# second pass: focus on successful nodes
apssh -o pass2 -t pass1/0ok/ -f elaborate-script.sh
```

* added the `--dry-run`/`-n` option to just see the selected nodes

## 0.0.6 - 2016 Sep 6

* added support for --script mylocalscript.sh arg1 arg2
* this will take care of copying over a local script in ~/.apssh
* before executing it remotely
* it is thus easier to handle composite shell commands, or any other python-like scripts

## 0.0.5 - 2016 Sep 5

* added support for --target "fit01 fit02" for smoother integration with $NODES on faraday

## 0.0.4 - 2016 Sep 1

* MANIFEST.in was missing

## 0.0.3 - 2016 Sep 1

* COPYING was missing

## 0.0.2 - 2016 Sep 1

* of course it did not go exactly as planned

## 0.0.1 - 2016 Sep 1

* first rough release

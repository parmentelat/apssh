# ChangeLog

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

# 0.2.6 - 2016 Sep 22

* class `SshJobCollector` can retrieve data

# 0.2.5 - 2016 Sep 22

* formatter cleanupmostly done
* all verbose reporting about connections and authentication and the like
  is now primarily done throuch asyncssh callbacks, except for sessions and sftp

# 0.2.4 - 2016 Sep 21

* big cleanup in formatters that can be verbose or not
* sshjobs uniformly refers to *node* rather than *proxy* including in attributes

# 0.2.3 - 2016 Sep 20

* exception handling :
  * more uniform way to write jobs, always let exceptions through
  * ending up in simpler code

# 0.2.2 - 2016 Sep 19

* add mutual exclusion locks to SshProxy connection and disconnection
  to ensure that an object gets connected only once

# 0.2.1 - 2016 Sep 19

* support for -g / --gateway option for 2-hops connections
* support for getting keys at the ssh agent if can be located
* tentatively fixes issue #2

# 0.1.1 - 2016 Sep 15

* add missing apssh.jobs to pypi packaging

# 0.1.0 - 2016 Sep 15

* fixes issue #1
* fixes SFTP closing
* addition of SshJobs to be used with asynciojobs

# 0.0.8 - 2016 Sep 8

* script mode still runs in remote home directory, does not cd in .apssh 

# 0.0.7 - 2016 Sep 7

* `--target` and `--exclude` can be used with a directory

  This is useful in combination with `--mark`, so that the second run can easily focus on successful nodes
  
```
# first pass to determine nodes that are responding
apssh -o pass1 --mark -t MYNODES hostname
# second pass: focus on successful nodes
apssh -o pass2 -t pass1/0ok/ -f elaborate-script.sh
```
  
* added the `--dry-run`/`-n` option to just see the selected nodes

# 0.0.6 - 2016 Sep 6

* added support for --script mylocalscript.sh arg1 arg2
* this will take care of copying over a local script in ~/.apssh
* before executing it remotely
* it is thus easier to handle composite shell commands, or any other python-like scripts

# 0.0.5 - 2016 Sep 5

* added support for --target "fit01 fit02" for smoother integration with $NODES on faraday

# 0.0.4 - 2016 Sep 1

* MANIFEST.in was missing

# 0.0.3 - 2016 Sep 1

* COPYING was missing

# 0.0.2 - 2016 Sep 1

* of course it did not go exactly as planned

# 0.0.1 - 2016 Sep 1

* first rough release

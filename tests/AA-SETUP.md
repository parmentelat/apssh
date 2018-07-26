# Test setup

## Historical setup

Before July 2018, the test code was targetting R2lab live, i.e.
  * a first ssh leg to `root@faraday.inria.fr`
  * a second hop to one or several nodes, e.g. `root@fit01`

## Current setup

Recommended now:

* create a VirtualBox VM based on ubuntu18
* create shared folder
  * so that guest can point at your `apssh` workdir
  * with auto-mount capability

```
    cd /media/sf_apssh
```

* create 2 network adapters
  * one using `NAT` (the VB default) so that the VM has Internet connectivity
  * one using `host-to-guest`

* open up ssh access
  * from host to guest as root; this one is used to log in manually but not by the test code; you might wish to write down the guest's IP address in your ssh client bookmarks
  * and **in loopback from root on guest to root on guest** - this si the one used by all tests

* install dependencies

```
pip3 install asyncssh asynciojobs orderedset psutil
apt-get install graphviz
pip3 install graphviz
```

* ***OPTIONAL***

It can be interesting to also share asynciojobs, and then define `PYTHONPATH` accordingly:

```
root@apssh-testbox:/media/sf_apssh# export PYTHONPATH=/media/sf_asynciojobs
```



* run tests as root on guest

```
root@apssh-testbox:/media/sf_apssh# python3 -m unittest tests.tests_connections
creating 5 commands on 1 connections to root@localhost
INITIAL count in=1 out=0
localhost:apssh-testbox
localhost:apssh-testbox
localhost:apssh-testbox
localhost:apssh-testbox
localhost:apssh-testbox
AFTER RUN in=2 out=1
AFTER CLEANUP in=1 out=0
.creating 5 commands on 5 connections to root@localhost
INITIAL count in=1 out=0
localhost:apssh-testbox
localhost:apssh-testbox
localhost:apssh-testbox
localhost:apssh-testbox
localhost:apssh-testbox
AFTER RUN in=6 out=5
AFTER CLEANUP in=1 out=0
.
----------------------------------------------------------------------
Ran 2 tests in 1.649s

OK
```

# Purpose

This tool aims at running commands remotely using ssh on a large number of target nodes at once. It it thus comparable to [parallel-ssh](https://code.google.com/p/parallel-ssh/) except that it is written on top of `asyncio` and `asyncssh`.

# Features

## scope selection

* to run the command `true` on hosts `host1` and `host2` as well on all hostnamed contained in file `file1`, do

#
    $ apssh -t host1 -f file1 -t host2 true
    
* Note that it's a good idea to separate the remote command after `--` so that python knows which options are intended for `apssh` and which are meant for the remote command

#
    $ apssh -t host1 -f file1 -t host2 -- rpm -aq \| grep libvirt
       
* specify a different username either globally or specifically; to use `user` on `host1` but `root` on `host2` and `host3`

#
    $ apssh -u root -t user@host1 -t host2 -t host3 -- true

* default key is as usual `~/.ssh/id_rsa`, but more keys can be used if necessary

#
    $ apssh -u root -f alive -i ~/.ssh/id_rsa -i ~/ple_debug.rsa -- grep VERSION_ID /etc/os-release
    
## max connections

* By default there is no limit on the number of simultaneous connections, which is likely to be a problem as soon as you go for several tens of hosts, as you would then run into limitations on open connections in your OS or network. To run at most 50 connections at a time

# 
    $ apssh -w 50 -f tons-of-nodes -- true

## output formats

* Default is to output every line coming back prefixed with hostname

# 
    $ apssh -u root -f alive -- grep VERSION_ID /etc/os-release
    host4.planetlab.informatik.tu-darmstadt.de@root:22 - Connection failed Disconnect Error: Permission denied
    host2.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
    host3.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
    planetlab1.xeno.cl.cam.ac.uk:VERSION_ID=23
    planetlab2.xeno.cl.cam.ac.uk:VERSION_ID=23
    
* Specifying `-o` is is possible to redirect outputs in a separate directory, in one file per hostname

# 
    $ apssh -o version-id -u root -f alive -- grep VERSION_ID /etc/os-release
    host4.planetlab.informatik.tu-darmstadt.de@root:22 - Connection failed Disconnect Error: Permission denied
    $ grep . version-id/*
    version-id/host2.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
    version-id/host3.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
    version-id/planetlab1.xeno.cl.cam.ac.uk:VERSION_ID=23
    version-id/planetlab2.xeno.cl.cam.ac.uk:VERSION_ID=23

* The `-d` option behaves like `-o` with a name computed from the current time

#
    $ date ; ./apssh.py -d -u root -f alive -- grep VERSION_ID /etc/os-release
    Tue Jan  5 14:58:43 CET 2016
    host4.planetlab.informatik.tu-darmstadt.de@root:22 - Connection failed Disconnect Error: Permission denied
    $ grep . 2016-01-05\@14\:58/*
    2016-01-05@14:58/host2.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
    2016-01-05@14:58/host3.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
    2016-01-05@14:58/planetlab1.xeno.cl.cam.ac.uk:VERSION_ID=23
    2016-01-05@14:58/planetlab2.xeno.cl.cam.ac.uk:VERSION_ID=23
    
# TODO

* investigate `socket.gaierror: [Errno 8] nodename nor servname provided, or not known`
* some kind of tests
* improve selection (merge -t and -f)
* add matching on hostnames
* some sort of stats : OK (return 0) KO (return something else) FAIL (cannot tell)
  * could be nice to store in files that can be used again by following calls
  
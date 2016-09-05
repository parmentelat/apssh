# Purpose

`apssh` is a tool that aims at running commands remotely using `ssh` on a large number of target nodes at once. It it thus comparable to [parallel-ssh](https://code.google.com/p/parallel-ssh/) except that it is written on top of `asyncio` and `asyncssh`.

# Features

## Scope selection

### Adding names : the `-t` or `--target` option

* to run the command `true` on hosts `host1` and `host2` as well on all hostnames contained in file `file1`, do this:

```
$ apssh -t host1 -t file1 -t host2 true
```    
* as you can see there is only one way to select a ***hostname or a filename*** that contains hostnames. If the string denotes an existing file, then it will open it to find hostnames; otherwise it will take it as a hostname - possibly prefixed with *user*`@`

### Excluding names : the `-x` or `--exclude` option    

* you can specify exclusions, the logic is exactly the same; exclusions are parsed first, and then the added hostnmes will be taken into account only if they are not excluded. Which means the order in which you define targets and excludes does not matter.

* so for example if you have all the known nodes in PLE in file `PLE.nodes`, and in a separate file `PLE.dns-unknown` the subset of the PLE nodes that are actually unknown to DNS, you can skip them by doing

```
$ apssh -u root -t PLE.nodes -x PLE.dns-unknown cat /etc/fedora-release
-- or, equivalently
$ apssh -u root -x PLE.dns-unknown -t PLE.nodes  cat /etc/fedora-release
```
## Remote command and user

### Good practice : use `--` before your command

First off, it's a good idea to separate the remote command after `--` so that python knows which options are intended for `apssh` and which are meant for the remote command

```
$ apssh -t host1 -t file1 -t host2 -- rpm -aq \| grep libvirt
```

### Running under a different user       
use ` --user` to specify a specific username globally; or give a specific user on a given hostname with `@`
  * so e.g. to use `user` on `host1` but `root` on `host2` and `host3`

```
$ apssh -u root -t user@host1 -t host2 -t host3 -- true
```

### Keys
Default key is as usual `~/.ssh/id_rsa`, but more keys can be used if necessary

```
$ apssh -u root -t alive -i ~/.ssh/id_rsa -i ~/ple_debug.rsa -- grep VERSION_ID /etc/os-release
```
    
## Max connections

By default there is no limit on the number of simultaneous connections, which is likely to be a problem as soon as you go for several tens of hosts, as you would then run into limitations on open connections in your OS or network. To run at most 50 connections at a time

```
$ apssh -w 50 -t tons-of-nodes -- true
```
## Output formats

### Default : on the fly, annotated with hostname
Default is to output every line as they come back, prefixed with associated hostname; this goes on stdout, with errors on stderr.

```
$ apssh -u root -t alive -- grep VERSION_ID /etc/os-release
host4.planetlab.informatik.tu-darmstadt.de@root:22 - Connection failed Disconnect Error: Permission denied
host2.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
host3.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
planetlab1.xeno.cl.cam.ac.uk:VERSION_ID=23
planetlab2.xeno.cl.cam.ac.uk:VERSION_ID=23
```
    
### Raw : on the fly, no annotation

With the `-r` or `--raw--` option, output is produced as it comes in, with no annotation as to which node the line is originating from.

### Subdir : store outputs individually in a dedicated dir

Alternatively, the `-o` or `-d` options allow to select a specific subdir and to store results in files named after each hostname. In this case, stdout is expected to contain a single line that specifies in which directory results are to be found.

* Specifying `-o` it is possible to redirect outputs in a separate directory, in one file per hostname
* The `-d` option behaves like `-o` with a name computed from the current time


```
$ ./apssh.py -d -u root -t alive -- cat /etc/fedora-release
2016-09-01@15:05
$ $ grep . 2016-09-01\@15\:05/*
2016-09-01@15:05/mars.planetlab.haw-hamburg.de:Fedora release 14 (Laughlin)
2016-09-01@15:05/merkur.planetlab.haw-hamburg.de:Fedora release 14 (Laughlin)
2016-09-01@15:05/planetlab-2.research.netlab.hut.fi:Fedora release 22 (Twenty Two)
2016-09-01@15:05/planetlab1.tlm.unavarra.es:Fedora release 22 (Twenty Two)
2016-09-01@15:05/planetlab1.virtues.fi:Fedora release 14 (Laughlin) 
```

* When an output subdir is selected, the `-s` or `--stamp` option can be used to request details on the retcod from individual nodes. The way this is exposed in is the filesystem under *<subdir>* as follows

  * *subdir*/`0ok`/*hostname* will contain 0 for all nodes that could run the command successfully
  * *subdir*/`1failed`/*hostname* will contain the actual retcod, for all nodes that were reached but could not successfully run the command, or `None` for the ones that were not reached at all.

In the example below, we try to talk to two nodes, one of which is not reachable. 


```
$ subdir=$(./apssh.py --stamp -d -u root -t planetlab2.tlm.unavarra.es -t uoepl2.essex.ac.uk cat /etc/fedora-release)
root@uoepl2.essex.ac.uk[22]:Connection failed:[Errno 8] nodename nor servname provided, or not known

$ echo $subdir
2016-09-01@15:42

$ head -100 $(find $subdir -type f)
==> 2016-09-01@15:42/0ok/planetlab2.tlm.unavarra.es <==
0

==> 2016-09-01@15:42/1failed/uoepl2.essex.ac.uk <==
None

==> 2016-09-01@15:42/planetlab2.tlm.unavarra.es <==
Fedora release 18 (Spherical Cow)
```

### Global retcod

`apssh` returns 0 if and only if all remote commands complete and return 0 themselves; otherwise it returns 1.    
    
# TODO

* some kind of tests
* add matching on hostnames

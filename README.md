# Purpose

`apssh` is a tool that aims at running commands remotely using `ssh` on a large number of target nodes at once. It is thus comparable to [parallel-ssh](https://code.google.com/p/parallel-ssh/), except that it is written on top of `asyncio` and `asyncssh`.

# How to get it

## Requirement
`apssh` requires python-3.5, as it uses the latest syntax constructions `async def` and `await` instead of the former `@asyncio.coroutine` and `yield from` idioms.

## Installation
```
[sudo] pip3 install apssh
```

# Features

## Usual mode

* The usual way to run a command that is already present on the remote systems, is to do e.g. this (we'll see the `-t` option right away)

```
apssh -t host1 -t host2 hostname
```

## Script mode : using a local script that gets copied over

* Now if you need to run a more convoluted command, you can of course quote meta characters as `;` and the like, and struggle you way using the same technique.
*  There is however an other way to achieve this, by writing a local file - say a shell script, but that can be any file that can run on the target nodes - in association with the `-s` a.k.a. `--script` option, like e.g.

```
apssh -t host1 -t host2 --script mymacros.sh one two
```

This will have the effect to perform the following on each target node :

* create if needed a directory named `~/.apssh` 
* copy the local file `mymacros.sh` into that remote dir
* run `.apssh/mymacros.sh one two` remotely in the home directory

Note that in this mode:

* the first argument of the commands part (here `mymacros.sh`) must denote a file that exists locally
* it does not have to sit in the local directory but will be installed right under `~/.apssh`
* the local file must be executable as `apssh` will preserve its permissions when pushing
* the command executed remotely has its *cwd* set to the remote home directory

## Scope selection

### Adding names : the `-t` or `--target` option

* to run the command `true` on hosts `host1` and `host2` as well on all hostnames contained in file `hosts.list`, do this:

```
$ apssh -t host1 -t hosts.list -t host2 true
```

* as a matter of fact you can use the `--target` option to refer to

  * the name of **an existing file**: in this case, the file is read, lines with a `#` are considered comments and ignored, all the rest is considered a list of hostnames; you can have several hostnames on one line if you want;
  * the name of **an existing directory**: in this case, all the simple files present in this directory are considered hostnames (See the `--mark` option below to see how this feature allows to refine a set of nodes to the ones that are actually reachable);
  * otherwise, the string is considered a hostname itself (or possibly several space-separated hostnames.

* So if directory `hosts.outputs` contains only 2 files named `tutu` and `toto`, and `hosts.file` is a text file containing this single line

```foo bar```

then if you run

```apssh -t host1 -t "host2 host3" -t hosts.file -t hosts.dir true```

will run `true` on hosts `host1`, `host2`, `host3`, `foo`, `bar`, `toto` and `tutu`.

### Excluding names : the `-x` or `--exclude` option    

* you can specify exclusions, the logic is exactly the same; exclusions are parsed first, and then the added hostnmes will be taken into account only if they are not excluded. Which means the order in which you define targets and excludes does not matter.

* so for example if you have all the known nodes in PLE in file `PLE.nodes`, and in a separate file `PLE.dns-unknown` the subset of the PLE nodes that are actually unknown to DNS, you can skip them by doing

```
$ apssh -u root -t PLE.nodes -x PLE.dns-unknown cat /etc/fedora-release
-- or, equivalently
$ apssh -u root -x PLE.dns-unknown -t PLE.nodes cat /etc/fedora-release
```

## Remote command and user

### Good practice : use `--` before your command

First off, it's a good idea to separate the remote command after `--` so that python knows which options are intended for `apssh` and which are meant for the remote command. 

In the example below, the `-aq` option is meant for the remote `rpm` command, so we insert a `--` before the command to avoid confusion

```
$ apssh -t host1 -t file1 -t host2 -- rpm -aq \| grep libvirt
```

### Running under a different user       
use ` --user` to specify a specific username globally; or give a specific user on a given hostname with `@`
  * so e.g. to run as `user` on `host1`, but as `root` on `host2` and `host3`

```
$ apssh -u root -t user@host1 -t host2 -t host3 -- true
```

### Keys
Default key is as usual `~/.ssh/id_rsa`, but more keys can be used if necessary with the `-i` or `--private-keys` options.

    
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
root@host4.planetlab.informatik.tu-darmstadt.de:22 - Connection failed Disconnect Error: Permission denied
host2.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
host3.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
planetlab1.xeno.cl.cam.ac.uk:VERSION_ID=23
planetlab2.xeno.cl.cam.ac.uk:VERSION_ID=23
```

In the above trasnscript, there were 5 target hostnames, one of which being unreachable. 
The line with `Permission denied` goes on *stderr*, the other ones on *stdout*.
    
### Raw : on the fly, no annotation

With the `-r` or `--raw--` option, output is produced as it comes in, so very much like with the default output, but with no annotation as to which node the line is originating from.

### Subdir : store outputs individually in a dedicated dir

Alternatively, the `-o` or `-d` options allow to select a specific subdir and to store results in files named after each hostname. In this case, *stdout* is expected to contain a single line that says in which directory results are to be found (this is useful mostly with `-d`, since with `-o` you can predict this in advance)

* Specifying `-o` it is possible to redirect outputs in a separate directory, in one file per hostname
* The `-d` option behaves like `-o` with a name computed from the current time


```
$ apssh -d -u root -t alive -- cat /etc/fedora-release
2016-09-01@15:05
$ $ grep . 2016-09-01\@15\:05/*
2016-09-01@15:05/mars.planetlab.haw-hamburg.de:Fedora release 14 (Laughlin)
2016-09-01@15:05/merkur.planetlab.haw-hamburg.de:Fedora release 14 (Laughlin)
2016-09-01@15:05/planetlab-2.research.netlab.hut.fi:Fedora release 22 (Twenty Two)
2016-09-01@15:05/planetlab1.tlm.unavarra.es:Fedora release 22 (Twenty Two)
2016-09-01@15:05/planetlab1.virtues.fi:Fedora release 14 (Laughlin) 
```

* When an output subdir is selected with either `-d` or `-o`, the `-m` or `--mark` option can be used to request details on the retcod from individual nodes. The way this is exposed in is the filesystem under *<subdir>* as follows

  * *subdir*/`0ok`/*hostname* will contain 0 for all nodes that could run the command successfully
  * *subdir*/`1failed`/*hostname* will contain the actual retcod, for all nodes that were reached but could not successfully run the command, or `None` for the nodes that were not reached at all.

In the example below, we try to talk to two nodes, one of which is not reachable. 


```
$ subdir=$(apssh --mark -d -u root -t planetlab2.tlm.unavarra.es -t uoepl2.essex.ac.uk cat /etc/fedora-release)
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
* probably a lot more features are required for more advanced usages.. Please send suggestions to *thierry dot parmentelat at inria.fr*

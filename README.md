# The `apssh` binary

## Purpose

`apssh` is a tool that aims at running commands remotely using `ssh` on a large
number of target nodes at once. It is thus comparable to
[parallel-ssh](https://code.google.com/p/parallel-ssh/), except that it is
written on top of `asyncio` and `asyncssh`.

In addition, `apssh` comes with a class `SshJob` that can be used in conjunction
with `asynciojobs` to write scenarios that are more elaborate than just sending
the same command on a bunch of hosts. This is presented in more details in
`README-jobs.md`.

This document, along with API reference doc, and changelog, is available at <http://apssh.readthedocs.io/>

## How to get it

### Requirement

`apssh` requires python-3.5, as it uses the latest syntax constructions `async
def` and `await` instead of the former `@asyncio.coroutine` and `yield from`
idioms.

### Installation
```
[sudo] pip3 install apssh
```

## 2 major modes : well-known commands, or local scripts

### Usual mode

The usual way to run a command that is **already present on the
remote systems**, is to do e.g. this (we'll see the `-t` option right away)

```
apssh -t host1 -t host2 hostname
```

### Script mode : using a local script that gets copied over

Now if you need to run a more convoluted command, you can of course quote meta
characters as `;` and the like, and struggle your way using the same technique.


There is however an other way to achieve this, by writing a **local script**
(usually a shell or python script) and use the `-s/--script` option, to have
`apssh` copy it on the target nodes before executing it, like e.g.:


```
apssh -t host1 -t host2 --script mymacros.sh one two
```

* You can also use this option and provide your own script
  directly on the command line

```
$ apssh -s -t r2lab.infra --script 'arg1=$1; shift; arg2=$1; shift; echo exchanged $arg2 $arg1' one two
faraday.inria.fr:exchanged two one
bemol.pl.sophia.inria.fr:exchanged two one
```


This will have the effect to perform the following on each target node :

* create if needed a directory named `~/.apssh-remote`
* copy the local file `mymacros.sh` - or your inline script - into that remote dir
* run `.apssh/mymacros.sh one two` remotely in the home directory

Note that in this mode:

* the first argument of the commands part (here `mymacros.sh`) should denote a
  file that exists locally, or be a valid script;
* it does not have to sit in the local directory but will be installed right
  under `~/.apssh-remote` regardless;
* the remote file will be created in mode o755;
* the command executed remotely has its *cwd* set to the remote home directory.

### Global return code

`apssh` returns 0 if and only if all remote commands complete and return 0
themselves; otherwise it returns 1.

## Scope selection

### Adding names : the `-t` or `--target` option

To run the command `true` on hosts `host1` and `host2` as well on all hostnames
contained in file `hosts.list`, do this:

```
$ apssh -t host1 -t hosts.list -t host2 true
```

As a matter of fact you can use the `--target` option to refer to

* the name of **an existing file**: in this case, the file is read, lines
  with a `#` are considered comments and ignored, all the rest is considered
  a list of hostnames; you can have several hostnames on one line if you want;
* the name of **an existing directory**: in this case, all the simple files
  present in this directory are considered hostnames (see the `--mark` option
  below to see how this feature allows to easily select nodes that are actually
  online and reachable);
* otherwise, the string is considered a hostname itself, or possibly several
  space-separated hostnames.
* **NOTE** that files and directories are also searched in `~/.apssh`,
  so that these shorthands can be defined globally.

So in practice, assuming that:
* directory `hosts.outputs` contains only 2 files named `tutu` and `toto`, and
* `hosts.file` is a text file containing the single line `foo bar`,

then if you run

```apssh -t host1 -t "host2 host3" -t hosts.file -t hosts.dir true```

it will cause the `true` command to be run on hosts `host1`, `host2`, `host3`,
`foo`, `bar`, `toto` and `tutu`.

### Excluding names : the `-x` or `--exclude` option    

You can specify exclusions, the logic is exactly the same; exclusions are parsed
first, and then hostnames from `--target` will be actually added only if they
are not excluded. Which means the order in which you define targets and excludes
does not matter.

So for example if you have all the known nodes in PLE in file `PLE.nodes`, and
in a separate file `PLE.dns-unknown` the subset of the PLE nodes that are
actually unknown to DNS, you can skip them by doing:

```
$ apssh -l root -t PLE.nodes -x PLE.dns-unknown cat /etc/fedora-release
```
or, equivalently:

```
$ apssh -l root -x PLE.dns-unknown -t PLE.nodes cat /etc/fedora-release
```

### Max connections: the `-w` or `--window` option

By default there is no limit on the number of simultaneous connections, which is
likely to be a problem as soon as you go for several tens of hosts, as you would
then run into limitations on open connections in your OS or network. Use `w` or
`--window` to run at most 50 connections at a time

```
$ apssh -w 50 -t tons-of-nodes true
```

## Users and keys

### Running under a different user       

Use `-l` or `--login` to specify a specific username globally; or give a
specific user on a given hostname with `@`

So e.g. to run as `user` on `host1`, but as `root` on `host2` and `host3`:

```
$ apssh -l root -t user@host1 -t host2 -t host3 -- true
```

### Keys

Here's how `apssh` locates private keys:

#### If no keys are specified using the `-i` command line option

* (A) if an *ssh agent* can be reached using the `SSH_AUTH_SOCK` environment
  variable, and offers a non-empty list of keys, `apssh` will use the keys
  loaded in the agent (**NOTE:** use `ssh-add` for managing the keys known to
  the agent);
* (B) otherwise, `apssh` will use `~/.ssh/id_rsa` and `~/.ssh/id_dsa`
  as far as they exist.

#### If keys are specified on the command line

* (C) That exact list is used for loading private keys.

#### In both cases

Note that when loading keys from a file - i.e. in cases (B) and (C) above, a
passphrase will be prompted at the terminal for each key that is
passphrase-protected. Each passphrase gets prompted once for all the target
hosts of course.

It results from all this that passphrase-protected keys can be used in `apssh`
without prompting **only if present in an agent**.

This behaviour might not be optimal - for example with this logic there is no
way to use agent-loaded keys **and** additional keys. I am eager to receive
feedback from users for possible improvements in this area.

## Gateway a.k.a. Bouncing a.k.a. Tunnelling

In some cases, the target nodes are not directly addressable from the box that
runs `apssh`, and the ssh traffic needs to go through a gateway. This typically
occurs with testbeds where nodes only have private addresses.

For example in the R2lab testbed, you cannot reach nodes directly from the
Internet, but you would need to issue something like:

```
# reaching one individual node with plain ssh
$ ssh onelab.inria.r2lab.admin@faraday.inria.fr ssh root@fit02 hostname
fit02
```

In such cases, you can specify the gateway username and hostname through the
`-g` or `--gateway` option. For example for running the above command on several
R2lab nodes in one `apssh` invokation:

```
$ apssh -g onelab.inria.r2lab.admin@faraday.inria.fr --login root -t "fit02 fit03 fit04" hostname
fit04:fit04
fit02:fit02
fit03:fit03
```

Note that in this case there is a single ssh connection created to the gateway.

## Output formats

### Default : on the fly, annotated with hostname

Default is to output every line as they come back, prefixed with associated
hostname. As you might expect, stdout goes to stdout and stderr to stderr.
Additionally, error messages issued by apssh itself, like e.g. when a host
cannot be reached, also goes on stderr.

```
$ apssh -l root -t alive -- grep VERSION_ID /etc/os-release
root@host4.planetlab.informatik.tu-darmstadt.de:22 - Connection failed Disconnect Error: Permission denied
host2.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
host3.planetlab.informatik.tu-darmstadt.de:VERSION_ID=23
planetlab1.xeno.cl.cam.ac.uk:VERSION_ID=23
planetlab2.xeno.cl.cam.ac.uk:VERSION_ID=23
```

In the above trasnscript, there were 5 target hostnames, one of which being
unreachable. The line with `Permission denied` goes on *stderr*, the other ones
on *stdout*.

### Your own format

You can specify a format with the `--format` option (see `apssh --help`); there
also are a few predefined formats for convenience:

* `-r/--raw` (equivalent to `--format '@line@'`) output is produced as it comes
 from the host, with no annotation as to which node the line is originating
 from.
* `-tc/--time-colon-format` is equivalent to `--format '%H-%M-%S:@host@:@line@'`.

### Subdir : store outputs individually in a dedicated dir

Alternatively, the `-o` or `-d` options allow to select a specific subdir and to
store results in files named after each hostname. In this case, *stdout* is
expected to contain a single line that says in which directory results are to be
found (this is useful mostly with `-d`, since with `-o` you can predict this in
advance)

* Specifying `-o` it is possible to redirect outputs in a separate directory,
  in one file per hostname.
* The `-d` option behaves like `-o` with a name computed from the current time.


```
$ rm -rf alive.results/
$ apssh -o alive.results -l root -t alive cat /etc/fedora-release
alive.results
$ grep . alive.results/*
alive.results/mars.planetlab.haw-hamburg.de:Fedora release 14 (Laughlin)
alive.results/merkur.planetlab.haw-hamburg.de:Fedora release 14 (Laughlin)
alive.results/planetlab-2.research.netlab.hut.fi:Fedora release 22 (Twenty Two)
alive.results/planetlab1.tlm.unavarra.es:Fedora release 22 (Twenty Two)
alive.results/planetlab1.virtues.fi:Fedora release 14 (Laughlin)
```

When an output subdir is selected with either `-d` or `-o`, the `-m` or `--mark`
option can be used to request details on the retcod from individual nodes. The
way this is exposed in the filesystem under *<subdir>* is as follows

* *subdir*/`0ok`/*hostname* will contain 0 for all nodes that could run the
  command successfully
* *subdir*/`1failed`/*hostname* will contain the actual retcod, for all nodes
 that were reached but could not successfully run the command, or `None`
 for the nodes that were not reached at all.

In the example below, we try to talk to two nodes, one of which is not
reachable.


```
$ subdir=$(apssh --mark -d -l root -t planetlab2.tlm.unavarra.es -t uoepl2.essex.ac.uk cat /etc/fedora-release)
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

### Good practices

* First off, **options order matters**; `apssh` will stop interpreting options
  on your command line at the beginning of the remote command. That is to say,
  in the following example

```
$ apssh -t host1 -t file1 -t host2 rpm -aq \| grep libvirt
```

the `-aq` option is meant for the remote `rpm` command, and that's fine because after the `rpm` token, `apssh` stops taking options, and passes them to the remote command instead.

* Also note in the example above that you can pass shell specials,
 like `|`, `<`, `>`, `;` and the like, by backslashing them, like this:

```
$ apssh -l root -t faraday.inria.fr -t r2lab.inria.fr uname -a \; cat /etc/fedora-release /etc/lsb-release 2\> /dev/null
r2lab.inria.fr:Linux r2lab.pl.sophia.inria.fr 4.6.4-201.fc23.x86_64 #1 SMP Tue Jul 12 11:43:59 UTC 2016 x86_64 x86_64 x86_64 GNU/Linux
r2lab.inria.fr:Fedora release 24 (Twenty Four)
faraday.inria.fr:Linux faraday 4.4.0-36-generic #55-Ubuntu SMP Thu Aug 11 18:01:55 UTC 2016 x86_64 x86_64 x86_64 GNU/Linux
faraday.inria.fr:DISTRIB_ID=Ubuntu
faraday.inria.fr:DISTRIB_RELEASE=16.04
faraday.inria.fr:DISTRIB_CODENAME=xenial
faraday.inria.fr:DISTRIB_DESCRIPTION="Ubuntu 16.04.1 LTS"
```

```
$ apssh -l root -t PLE.alive.5 -tc uname -r \; hostname
16-47-40:mars.planetlab.haw-hamburg.de:2.6.32-36.onelab.i686
16-47-40:merkur.planetlab.haw-hamburg.de:2.6.32-36.onelab.i686
16-47-40:mars.planetlab.haw-hamburg.de:mars.planetlab.haw-hamburg.de
16-47-40:merkur.planetlab.haw-hamburg.de:merkur.planetlab.haw-hamburg.de
16-47-40:planetlab1.tlm.unavarra.es:4.4.13-200.fc22.x86_64
16-47-40:planetlab1.tlm.unavarra.es:planetlab1.tlm.unavarra.es
16-47-40:planetlab1.virtues.fi:2.6.32-36.onelab.i686
16-47-40:planetlab1.virtues.fi:planetlab1.virtues.fi
16-47-40:planetlab-2.research.netlab.hut.fi:4.2.3-200.fc22.x86_64
16-47-40:planetlab-2.research.netlab.hut.fi:planetlab-2.research.netlab.hut.fi
```

## TODO

* brewing something like `appush` and `appull` sounds pretty straightforward,
  and could turn out most useful; some day probably
* current output system can only properly handle commands output that are
  **text-based**; if your remote command produces binary data instead,
  you must redirect its output on the remote system, and fetch the results
  later on; note that the binary command `apssh` has no option for doing that,
  but the API has 2 objects `Pull` and `Push` for doing this in a more
  elaborate scenario (see README-jobs.md).
* better tests coverage would not hurt !?!
* probably a lot more features are required for more advanced usages,
 feel free to fill in issues at <https://github.com/parmentelat/apssh>.

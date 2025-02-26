# Test setup - redeux 2024 Dec - using UTM and uv

**WARNING** all this is a little fragile; for example some tests monitor the
number of active processes and expect its size to change by some fixed amount
bottom line is, these cannot run in parallel, for example it is not supported to
run the tests for 2 flavours of Python at the same time on a given box

## how to use

### synopsys

```bash
ssh -Y root@apssh-test
```

then on the guest

```bash
cd /media/git/apssh
source .venv/bin/activate
pytest
```

### caveat

somehow after a while, the sshd does not answer anymore; the VM needs a restart

## how to install the UTM guest

### raw install

* used UTM to create a brand new fedora41 box
* installed from netinst ISO
  * came with python (3.13) installed; added `git` and `emacs-nox`
* chose to share the whole `~/git/` folder under `/media/git`
  * https://docs.getutm.app/guest-support/linux/#virtfs
  * it's all in `/etc/fstab` in the guest
  * not quite sure whether `dnf install virtiofsd` was required or not
* installed `uv` with
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  at that point `uv` sees the preinstalled python3.13

### the `apsshuser` user

* do not forget to create this user, with the same authorized keys as root, as it is used in the tests

### miscell `dnf` installs

```bash
dnf install -y graphviz gcc tcpdump git 
# for X11 forwarding - xterm is useful for tests
dnf install -y xorg-x11-server-Xorg xorg-x11-xauth xterm
```

### reaching the box

* find out the right IP address with `ip add sh` on the guest
* created an iTerm profile to connect to it - don't forget the `-Y` option for X11 forwarding
* for convience only, in the host, I added an entry for the new box `/etc/hosts`:
  ```
  192.168.64.7  apssh-test
  ```

### `X11` forwarding

* was not working at first, so:
* in the host: I cleaned up the `known_hosts` file for the new box:
  ```
  ssh-keygen -R apssh-test
  ```

### messed about with `uv` while getting to know it

* ran into some kind of trap with `pytest`:
  * `uv tool install pytest` apparently installs `pytest` systemwide
  * **BUT** then running the tests fails and consistently does not find dependent modules
  * so I had to `pip install pytest` in the venv instead
* the equivalent of `pip install -r requirements.txt` is now
  * `uv pip install -r pyproject.toml`
* `uv tree` is nice, it shows the resolved deps with their versions

----
----

## OLDER STUFF 

all the rest is now obsolete and kept just in case only

----
----

### base image

* create a VirtualBox VM based ~~on ubuntu18~~  
  ***update sep 2022*** now using fedora 36
* using fedora-server - minimal distrib
* root as the usual onelab passwd

### VB settings

* create shared folders
  * so that guest can point at the sources
  * with auto-mount capability

    | host | guest |
    |-|-|
    | `~/git/apssh` | `/media/sf_apssh` |
    | `~/git/sf_asynciojobs` | `/media/sf_asynciojobs` |

* create 2 network adapters
  * one using `NAT` (the VB default) so that the VM has Internet connectivity
  * one using `host-to-guest`

### linux settings

* open up ssh access
  * from host to guest as root; this one is used to log in manually but not by
    the test code; you might wish to write down the guest's IP address in your
    ssh client bookmarks  
    (like e.g. `192.168.56.104`)
  * and **in loopback from root on guest to root on guest** - this is the one
    used by all tests

  * initialize known_hosts
    ```bash
    ssh localhost hostname
    ```

***from there, use iterm to login as it will support cut'n paste***

* guest additions are required (and a reboot too) for the shared folders to appear

  ```bash
  dnf install -y virtualbox-guest-additions
  ```

* install miniconda

  ```bash
  cd /tmp
  curl -O https://repo.anaconda.com/miniconda/Miniconda3-py39_4.12.0-Linux-x86_64.sh
  bash Miniconda3-py39_4.12.0-Linux-x86_64.sh
  ```

***reboot for the guest-additions to kick in***

* dnf installs

  ```bash
  dnf install -y graphviz gcc tcpdump git 
  # for X11 forwarding - xterm is useful for tests
  dnf install -y xorg-x11-server-Xorg xorg-x11-xauth xterm
  ```

### conda envs

* create and fill a conda env, e.g. to test on python3.9

  ```bash
  conda create -n py39 python=3.9
  conda activate py39
  pip install psutil orderedset graphviz pytest
  pip install -e /media/sf_asynciojobs /media/sf_apssh
  ```
* use it to run tests

  ```bash
  conda activate py39
  cd /media/sf_apssh
  pytest   # or make tests
  ```

### sample output

```bash
[root@fedora sf_asynciojobs]# pytest
============================================================== test session starts ==============================================================
platform linux -- Python 3.10.6, pytest-7.1.3, pluggy-1.0.0
rootdir: /media/sf_asynciojobs
collected 59 items

tests/test_basics.py .........................                                                                                            [ 42%]
tests/test_bypass.py .......                                                                                                              [ 54%]
tests/test_cycles.py ..                                                                                                                   [ 57%]
tests/test_graph.py ..                                                                                                                    [ 61%]
tests/test_nesting.py .......                                                                                                             [ 72%]
tests/test_png.py ......                                                                                                                  [ 83%]
tests/test_shutdown.py ..........                                                                                                         [100%]

=============================================================== warnings summary ================================================================
tests/test_basics.py: 20 warnings
tests/test_graph.py: 1 warning
tests/test_nesting.py: 16 warnings
tests/test_shutdown.py: 10 warnings

<snip>

======================================================= 59 passed, 74 warnings in 40.71s ========================================================
sys:1: RuntimeWarning: coroutine 'aprint' was never awaited
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
[root@fedora sf_asynciojobs]#
```

# iteration 1 : use apssh's sshproxy as-is
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes whose output is text-based 
# but well, right now I'm in a rush and would want to see stuff running...

import os.path
import random

from asyncssh import EXTENDED_DATA_STDERR

from apssh.sshproxy import SshProxy
from apssh import load_agent_keys
from apssh.config import default_remote_workdir

from asynciojobs.job import AbstractJob

####################
# The base class for items that make a SshJob's commands
class AbstractCommand:

    def __repr__(self):
        return "<{}: {}>".format(type(self).__name__, self.command())

    ### 
    async def co_run_remote(self, node):
        """
        needs to be redefined
        should return 0 if everything is fine
        """
        pass

    # descriptive views, required by SshJob
    def details(self):
        "used by SshJob to conveniently show the inside of a Job"
        return "AbstractCommand.details needs to be redefined"

    # extra messages go to stderr and are normally formatted
    def _verbose_message(self, node, message):
        if not hasattr(self, 'verbose') or not self.verbose:
            return
        if not message.endswith("\n"):
            message += "\n"
        node.formatter.line(message, EXTENDED_DATA_STDERR, node.hostname)

##### The usual
class Run(AbstractCommand):
    """
    The most basic form of a command is to .. run a remote command
        
    Example         `Run("tail", "-n", 1, "/etc/lsb-release")`
    or equivalently `Run("tail -n 1 /etc/lsb-release")`

    The actual command run remotely is obtained by 
    concatenating the string representation of each argv
    and separating them with a space

    If verbose is set, the actual command being run is printed out

    """

    def __init__(self, *argv, verbose = False):
        self.argv = argv
        self.verbose = verbose
        
    def details(self):
        return self.command()

    def command(self):
        # build the (remote) command to invoke
        return " ".join( str(x) for x in self.argv )

    async def co_run_remote(self, node):
        self._verbose_message(node, "Run: -> {}".format(self.command()))
        # need an ssh connection
        connected = await node.connect_lazy()
        if not connected:
            return 
        node_run = await node.run(self.command())
        self._verbose_message(node, "Run: {} <- {}".format(node_run, self.command()))
        return node_run

    async def co_run_local(self, localnode):
        self._verbose_message(localnode, "Run: -> {}".format(self.command()))
        retcod = await localnode.run(self.command())
        self._verbose_message(localnode, "Run: {} <- {}".format(retcod, self.command()))
        return retcod

##### same but using a script that is available as a local file
class RunScript(AbstractCommand):
    """
    A class to run a **local script file** on the remote system, 
    but with arguments passed exactly like with `Run`

    Example:

    run a local script located in ../foo.sh with specified args:
        RunScript("../foo.sh", "arg1", 2, "arg3")

    includes allows to specify a list of local files 
    that need to be copied over at the same location as the local script
    i.e. typically in ~/.apssh-remote
    
    if verbose is set, the remote script is run through `bash -x`

    preserve and follow_symlinks are accessories to file transfer 
    (when local script gets pushed over), see this page for their meaning

    http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.put
    """
    def __init__(self, local_script, *args, includes = None,
                 # when copying the script and includes over
                 preserve = True, follow_symlinks = True,
                 # if this is set, run bash -x
                 verbose = False):
        self.local_script = local_script
        self.includes = includes
        self.follow_symlinks = follow_symlinks
        self.preserve = preserve
        self.verbose = verbose
        self.args = args
        ###
        self.basename = os.path.basename(local_script)

    def command(self, with_path=False):
        simple = self.basename + " " + " ".join(str(x) for x in self.args)
        # without path is for details() and similar
        if not with_path:
            return simple
        actual = default_remote_workdir + "/" + simple
        if self.verbose:
            actual = "bash -x " + actual
        return actual

    def details(self):
        return self.command() + " (local script pushed and executed)" 

    async def co_run_remote(self, node):
        # we need the node to be connected by ssh and SFTP
        remote_path =  default_remote_workdir + "/" + self.basename
        if not os.path.exists(self.local_script):
            print("RunScript : {} not found - bailing out"
                  .format(self.local_script))
            return
        self._verbose_message(node, "RunScript: pushing script into {}".format(remote_path))
        if not ( await node.sftp_connect_lazy() 
                 and await node.mkdir(default_remote_workdir) 
                 and await node.put_file_s(
                     self.local_script, remote_path)):
            return
        # make sure the remote script is executable - chmod 755
        permissions = 0o755
        await node.sftp_client.chmod(remote_path, permissions)
        
        if self.includes:
            # sequential is good enough
            for include in self.includes:
                if not os.path.exists(include):
                    print("include file {} not found -- skipped".format(include))
                    continue
                self._verbose_message(node, "RunScript: pushing include {} in {}"
                                      .format(include, default_remote_workdir))
                if not await node.put_file_s(
                        include, default_remote_workdir + "/",
                        follow_symlinks = self.follow_symlinks,
                        preserve = self.preserve):
                    return
        command = self.command(with_path=True)
        self._verbose_message(node, "RunScript: -> {}".format(command))
        node_run = await node.run(command)
        self._verbose_message(node, "RunScript: {} <- {}".format(node_run, command))
        return node_run

#####
class RunString(AbstractCommand):
    """
    Much like RunScript, but the script to run remotely is expected
    to be passed in the first argument as **a python string** this time.

    `remote_name`, if provided, will tell how the created script
    should be named on the remote node - it is randomly generated if not specified

    `includes` allows to specify a list of local files 
    that need to be copied over at the same location as the local script
    i.e. typically in ~/.apssh-remote

    if `verbose` is set, the remote script is run through `bash -x`

    Example:

    myscript = "#!/bin/bash\nfor arg in "$@"; do echo arg=$arg; done"
    RunString(myscript, "foo", "bar", 2, "arg3", remote_name = "echo-args.sh")
    
    """

    @staticmethod
    def random_id():
        return "".join(random.choice('abcdefghijklmnopqrstuvwxyz') 
            for i in range(8))
    
    def __init__(self, script_body, *args, includes = None,
                 # the name under which the remote command will be installed
                 remote_name = None,
                 # if this is set, run bash -x
                 verbose = False):
        self.script_body = script_body
        self.includes = includes
        self.args = args
        self.remote_name = remote_name or self.random_id()
        self.verbose = verbose
        # just in case
        self.remote_name = os.path.basename(self.remote_name)

    # if it's small let's show it all
    def details(self):
        lines = self.script_body.split("\n")
        if len(lines) > 6:
            return self.command() + " (string script installed and executed)"
        else:
            result = "Following script called with args "
            result += " ".join('"{}"'.format(arg) for arg in self.args) + "\n"
            result += self.script_body
            return result
    
    def command(self, with_path=False):
        simple = self.remote_name + " " + " ".join(str(x) for x in self.args)
        # without path is for details() and similar
        if not with_path:
            return simple
        actual = default_remote_workdir + "/" + simple if with_path else simple
        if self.verbose:
            actual = "bash -x " + actual
        return actual

    async def co_run_remote(self, node):
        """we need the node to be connected by ssh and SFTP"""
        remote_path = default_remote_workdir + "/" + self.remote_name
        self._verbose_message(node, "RunString: pushing script into {}".format(remote_path))
        if not ( await node.sftp_connect_lazy() 
                 and await node.mkdir(default_remote_workdir) 
                 and await node.put_string_script(
                     self.script_body,
                     remote_path)):
            return
        if self.includes:
            # sequential is good enough
            for include in self.includes:
                if not os.path.exists(include):
                    print("include file {} not found -- skipped".format(include))
                self._verbose_message(node, "RunString: pushing include {} in {}"
                                      .format(include, default_remote_workdir))
                if not await node.put_file_s(
                        include, default_remote_workdir + "/"):
                    return

        command = self.command(with_path=True)
        self._verbose_message(node, "RunString: -> {}".format(command))
        node_run = await node.run(command)
        self._verbose_message(node, "RunString: {} <- {}".format(node_run, command))
        return node_run

####
class Pull(AbstractCommand):
    """
    Retrieve remote files and stores them locally
    """

    def __init__(self, remotepaths, localpath,
                 verbose = False,
                 # asyncssh's SFTP client get options
                 *args, **kwds):
        self.remotepaths = remotepaths
        self.localpath = localpath
        self.verbose = verbose
        self.args = args
        self.kwds = kwds

    def remote_path(self):
        paths = self.remotepaths
        if isinstance(self.remotepaths, str):
            paths = [ paths ]
        return "remote path {}".format(paths[0]) \
            if len(paths) == 1 \
               else "{} remote path(s) starting with {}"\
                   .format(len(self.remotepaths), self.remotepaths[0])

    def details(self):
        return "Pull {} into {}".\
            format(self.remote_path(), self.localpath)

    async def co_run_remote(self, node):
        self._verbose_message(node, "Pull: remotepaths={}, localpath={}"
                              .format(self.remotepaths, self.localpath))
        await node.sftp_connect_lazy()
        await node.get_file_s(self.remotepaths, self.localpath,
                              *self.args, **self.kwds)
        self._verbose_message(node, "Pull done")
        return 0


####
class Push(AbstractCommand):
    """
    Put local files onto target node
    """

    def __init__(self, localpaths, remotepath,
                 verbose = False,
                 # asyncssh's SFTP client put option
                 *args, **kwds):
        self.localpaths = localpaths
        self.remotepath = remotepath
        self.verbose = verbose
        self.args = args
        self.kwds = kwds

    def local_path(self):
        paths = self.localpaths
        if isinstance(self.localpaths, str):
            paths = [ paths ]
        return "local path {}".format(paths[0]) \
            if len(paths) == 1 \
               else "{} local path(s) starting with {}"\
                   .format(len(self.localpaths), self.localpaths[0])

    def details(self):
        return "push {} onto {}".\
            format(self.local_path(), self.remotepath)
        
    async def co_run_remote(self, node):
        self._verbose_message(node, "Push: localpaths={}, remotepath={}"
                             .format(self.localpaths, self.remotepath))
        await node.sftp_connect_lazy()
        await node.put_file_s(self.localpaths, self.remotepath,
                              *self.args, **self.kwds)
        self._verbose_message(node, "Push done")
        return 0

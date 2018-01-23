# iteration 1 : use apssh's sshproxy as-is
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes whose output is text-based
# but well, right now I'm in a rush and would want to see stuff running...

from pathlib import Path
import random

from asyncssh import EXTENDED_DATA_STDERR

from apssh.sshproxy import SshProxy
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

    setting `x11=True` enables X11 forwarding, so a X11 program
    running remotely ends on the local DISPLAY

    If verbose is set, the actual command being run is printed out

    """

    # it was tempting to use x11_forwarding as the name here, but
    # first it's definitely too long, given the usage of Run
    # plus, maybe some day we'll need to add other keywords
    # to create_connection than just x11_forwarding,
    # so, it feels about right to call this just like x11
    def __init__(self, *argv, verbose=False, x11=False):
        self.argv = argv
        self.verbose = verbose
        self.x11 = x11

    def details(self):
        return self.command()

    def command(self):
        # build the (remote) command to invoke
        return " ".join(str(x) for x in self.argv)

    async def co_run_remote(self, node):
        self._verbose_message(node, "Run: -> {}".format(self.command()))
        # need an ssh connection
        connected = await node.connect_lazy()
        if not connected:
            return
        node_run = await node.run(self.command(), x11_forwarding=self.x11)
        self._verbose_message(
            node, "Run: {} <- {}".format(node_run, self.command()))
        return node_run

    async def co_run_local(self, localnode):
        self._verbose_message(localnode, "Run: -> {}".format(self.command()))
        retcod = await localnode.run(self.command())
        self._verbose_message(
            localnode, "Run: {} <- {}".format(retcod, self.command()))
        return retcod

##### the base class for running a script provided locally
# same as Run, but the command to run remotely is provided
# as a local material, either a local file, or a python string


class RunLocalStuff(AbstractCommand):
    """
    The base class for RunScript and RunString.

    verbose = True means running the script with "bash -x" 
    which admittedly is a little hacky

    Both classes need to generate random names for the remote command.
    This is because 2 parallel runs of the same command would otherwise
    be at risk of one overwriting the remote command file, while the second
    tries to run it, which causes errors like this

    fit26:bash: .apssh-remote/B3-wireless.sh: /bin/bash: bad interpreter: Text file busy
    """

    def __init__(self, args, includes, verbose, remote_basename, x11):
        self.args = args
        self.includes = includes
        self.verbose = verbose
        self.remote_basename = remote_basename
        self.x11 = x11

    def _random_id(self):
        """
        Generate a random string to avoid conflicting names 
        on the remote host
        """
        return "".join(random.choice('abcdefghijklmnopqrstuvwxyz')
                       for i in range(8))

    def _args_line(self):
        return " ".join(str(x) for x in self.args)

    def command(self):
        """
        The command to run remotely
        """
        command = self.remote_basename + " " + self._args_line()
        command = default_remote_workdir + "/" + command
        if self.verbose:
            command = "bash -x " + command
        return command

    async def co_run_remote(self, node):
        """
        The common behaviour for both classes is as follows

        Method co_install(self) is invoked to push the local material
        over in default_remote_workdir/self.remote_basename
        it should raise an exception in case of failure
        """
        # we need the node to be connected by ssh and SFTP
        # and we need the remote work dir to be created
        if not (await node.sftp_connect_lazy()
                and await node.mkdir(default_remote_workdir)):
            # should never be here
            return

        remote_path = default_remote_workdir + "/" + self.remote_basename

        # do the remote install - depending on the actual class
        await self.co_install(node, remote_path)

        # make sure the remote script is executable - chmod 755
        permissions = 0o755
        await node.sftp_client.chmod(remote_path, permissions)

        if self.includes:
            # sequential is good enough
            for include in self.includes:
                if not Path(include).exists():
                    print("include file {} not found -- skipped".format(include))
                    continue
                self._verbose_message(node, "RunLocalStuff: pushing include {} in {}"
                                      .format(include, default_remote_workdir))
                if not await node.put_file_s(
                        include, default_remote_workdir + "/",
                        follow_symlinks=True):
                    return

        # trigger it
        command = self.command()
        self._verbose_message(node, "RunLocalStuff: -> {}".format(command))
        node_run = await node.run(command, x11_forwarding=self.x11)
        self._verbose_message(
            node, "RunLocalStuff: {} <- {}".format(node_run, command))
        return node_run


# same but using a script that is available as a local file
class RunScript(RunLocalStuff):
    """
    A class to run a **local script file** on the remote system, 
    but with arguments passed exactly like with `Run`

    Example:

    run a local script located in ../foo.sh with specified args:
        RunScript("../foo.sh", "arg1", 2, "arg3")

    includes allows to specify a list of local files 
    that need to be copied over at the same location as the local script
    i.e. typically in ~/.apssh-remote

    setting `x11=True` enables X11 forwarding

    if verbose is set, the remote script is run through `bash -x`

    """

    def __init__(self, local_script, *args, includes=None, x11=False,
                 # if this is set, run bash -x
                 verbose=False):
        self.local_script = local_script
        self.local_basename = Path(local_script).name
        remote_basename = self.local_basename + '-' + self._random_id()

        super().__init__(args, includes, verbose, remote_basename, x11)

    def details(self):
        return "RunScript: " + self.local_basename + " " + self._args_line()

    async def co_install(self, node, remote_path):
        if not Path(self.local_script).exists():
            raise OSError("RunScript : {} not found - bailing out"
                          .format(self.local_script))
        if not await node.put_file_s(
                self.local_script, remote_path,
                follow_symlinks=True):
            return

#####


class RunString(RunLocalStuff):
    """
    Much like RunScript, but the script to run remotely is expected
    to be passed in the first argument as **a python string** this time.

    `remote_name`, if provided, will tell how the created script
    should be named on the remote node - it is randomly generated if not specified

    `includes` allows to specify a list of local files 
    that need to be copied over at the same location as the local script
    i.e. typically in ~/.apssh-remote

    setting `x11=True` enables X11 forwarding

    if `verbose` is set, the remote script is run through `bash -x`

    Example:

    myscript = "#!/bin/bash\nfor arg in "$@"; do echo arg=$arg; done"
    RunString(myscript, "foo", "bar", 2, "arg3", remote_name = "echo-args.sh")

    """

    def __init__(self, script_body, *args, includes=None, x11=False,
                 # the name under which the remote command will be installed
                 remote_name=None,
                 # if this is set, run bash -x
                 verbose=False):
        self.script_body = script_body
        if remote_name:
            self.remote_name = remote_name
            # just in case
            remote_basename = Path(self.remote_name).name
            remote_basename += '-' + self._random_id()
        else:
            self.remote_name = ''
            remote_basename = self._random_id()
        super().__init__(args, includes, verbose, remote_basename, x11)

    # if it's small let's show it all
    def details(self):
        if self.remote_name:
            return "RunString: " + self.remote_name + " " + self._args_line()
        else:
            lines = self.script_body.split("\n")
            if len(lines) > 4:
                return "RunString: " + self.remote_basename + " " + self._args_line()
            else:
                result  = "RunString: following script called with args "
                result += self._args_line() + "\n"
                result += self.script_body
                result += "***"
                return result

    async def co_install(self, node, remote_path):
        self._verbose_message(
            node, "RunString: pushing script into {}".format(remote_path))
        if not await node.put_string_script(
                self.script_body, remote_path):
            return

####


class Pull(AbstractCommand):
    """
    Retrieve remote files and stores them locally

    See also:
    http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.get

    """

    def __init__(self, remotepaths, localpath,
                 verbose=False,
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
            paths = [paths]
        return "remote path {}".format(paths[0]) \
            if len(paths) == 1 \
               else "{} remote path(s) starting with {}"\
            .format(len(self.remotepaths), self.remotepaths[0])

    def details(self):
        return "Pull: {} into {}".\
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

    See also:
    http://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SFTPClient.put

    """

    def __init__(self, localpaths, remotepath,
                 verbose=False,
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
            paths = [paths]
        return "local path {}".format(paths[0]) \
            if len(paths) == 1 \
               else "{} local path(s) starting with {}"\
            .format(len(self.localpaths), self.localpaths[0])

    def details(self):
        return "Push: {} onto {}".\
            format(self.local_path(), self.remotepath)

    async def co_run_remote(self, node):
        self._verbose_message(node, "Push: localpaths={}, remotepath={}"
                              .format(self.localpaths, self.remotepath))
        await node.sftp_connect_lazy()
        await node.put_file_s(self.localpaths, self.remotepath,
                              *self.args, **self.kwds)
        self._verbose_message(node, "Push done")
        return 0

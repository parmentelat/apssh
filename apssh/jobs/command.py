# iteration 1 : use apssh's sshproxy as-is
# the thing is, this implementation relies on formatters
# which probably needs more work.
# in particular this works fine only with remote processes whose output is text-based 
# but well, right now I'm in a rush and would want to see stuff running...

import os.path

from apssh.sshproxy import SshProxy
from apssh import load_agent_keys
from apssh.config import default_remote_workdir

from asynciojobs.job import AbstractJob

####################
class AbstractCommand:
    """
    The base class for items that make a SshJob's commands
    """

    def __repr__(self):
        return "<{}: {}>".format(type(self).__name__, self.command())

    async def co_exec(self, node):
        "needs to be redefined"
        pass

    async def co_prepare(self, node):
        "needs to be redefined" 
        pass

    # descriptive views, required by SshJob
    def command(self):
        """a one-liner please"""
        return "AbstractCommand.command needs to be redefined"
        
    def details(self):
        """up to 4-5 lines or so"""
        return "AbstractCommand.details needs to be redefined"

    def default_label(self):
        """up to 30 chars seems reasonable"""
        return "AbstractCommand.default_label() needs to be redefined"


##### The usual
class Command(AbstractCommand):

    def __init__(self, *argv):
        """
        Example         Command("tail", "-n", 1, "/etc/lsb-release")
        or equivalently Command("tail -n 1 /etc/lsb-release")
        """
        print("Command.__init__ ->", argv)
        self.argv = argv
        
    def command(self):
        """build the (remote) command to invoke"""
        return " ".join( str(x) for x in self.argv )

    async def co_prepare(self, node):
        """we need to node to be connected"""
        connected = await node.connect_lazy()
        return connected

    async def co_exec(self, node):
        data = await node.run(self.command())
        return data

##### same but using a script that is available as a local file
class LocalScript(AbstractCommand):
    def __init__(self, local_script, *args, includes = None,
                 # when copying the script and includes over
                 preserve = True, follow_symlinks = True):
        """
        Example
        run a local script located in ../foo.sh with specified args:
                        LocalScript("../foo.sh", "arg1", 2, "arg3")

        includes allows to specify a list of local files 
        that need to be copied over at the same location as the local script
        i.e. typically in ~/.apssh-remote
        """
        self.local_script = local_script
        self.includes = includes
        self.follow_symlinks = follow_symlinks
        self.preserve = preserve
        self.args = args
        ###
        self.basename = os.path.basename(local_script)

    def command(self, with_path=False):
        simple = self.basename + " " + " ".join( str(x) for x in self.args)
        return default_remote_workdir + "/" + simple if with_path else simple

    async def co_prepare(self, node):
        """we need to node to be connected by ssh and SFTP"""
        if not os.path.exists(self.local_script):
            print("LocalScript : {} not found - bailing out"
                  .format(self.local_script))
            return
        if not ( await node.sftp_connect_lazy() 
                 and await node.mkdir(default_remote_workdir) 
                 and await node.put_file_s(
                     self.local_script, default_remote_workdir+"/",
                     follow_symlinks = self.follow_symlinks,
                     preserve = self.preserve)):
            return
        if self.includes:
            # sequential is good enough
            for include in self.includes:
                if not os.path.exists(include):
                    print("include file {} not found -- skipped".format(include))
                if not await node.put_file_s(
                        include, default_remote_workdir+"/",
                        follow_symlinks = self.follow_symlinks,
                        preserve = self.preserve):
                    return
        return True

    async def co_exec(self, node):
        data = await node.run(self.command(with_path=True))
        return data

#####
class StringScript(AbstractCommand):
    def __init__(self, script_body, *args, includes = None,
                 # the name under which the remote command will be installed
                 remote_name = None,
                 # when copying the script and includes over
                 preserve = True, follow_symlinks = True):
        """
        Example
        run a local script located in ../foo.sh with specified args:
                        LocalScript("../foo.sh", "arg1", 2, "arg3")

        includes allows to specify a list of local files 
        that need to be copied over at the same location as the local script
        i.e. typically in ~/.apssh-remote
        """
        self.local_script = local_script
        self.includes = includes
        self.follow_symlinks = follow_symlinks
        self.preserve = preserve
        self.args = args
        ###
        self.basename = os.path.basename(local_script)

    # xxx NOT FINISHED
    
    def command(self, with_path=False):
        simple = self.basename + " " + " ".join( str(x) for x in self.args)
        return default_remote_workdir + "/" + simple if with_path else simple

    async def co_prepare(self, node):
        """we need to node to be connected by ssh and SFTP"""
        if not os.path.exists(self.local_script):
            print("LocalScript : {} not found - bailing out"
                  .format(self.local_script))
            return
        if not ( await node.sftp_connect_lazy() 
                 and await node.mkdir(default_remote_workdir) 
                 and await node.put_file_s(
                     self.local_script, default_remote_workdir+"/",
                     follow_symlinks = self.follow_symlinks,
                     preserve = self.preserve)):
            return
        if self.includes:
            # sequential is good enough
            for include in self.includes:
                if not os.path.exists(include):
                    print("include file {} not found -- skipped".format(include))
                if not await node.put_file_s(
                        include, default_remote_workdir+"/",
                        follow_symlinks = self.follow_symlinks,
                        preserve = self.preserve):
                    return
        return True

    async def co_exec(self, node):
        data = await node.run(self.command(with_path=True))
        return data

    

import os.path

from asynciojobs.job import AbstractJob

########################################
########################################
########################################
class SshJobCollector(AbstractJob):
    """
    Retrieve remote files and stores them locally
    """

    def __init__(self, node, remotepaths, localpath,
                 # set to False if not set explicitly here
                 forever = None,
                 # set to True if not set explicitly here
                 critical = None,
                 # asyncssh's SFTP client get option
                 preserve = False, recurse = False, follow_symlinks = False,
                 # this goes to AbstractJob
                 *args, **kwds):
        self.node = node
        self.remotepaths = remotepaths
        self.localpath = localpath
        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        self.preserve = preserve
        self.recurse = recurse
        self.follow_symlinks = follow_symlinks
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

    async def co_run(self):
        await self.node.get_file_s(self.remotepaths, self.localpath,
                                   preserve = self.preserve,
                                   recurse = self.recurse,
                                   follow_symlinks = self.follow_symlinks)

    async def co_shutdown(self):
        await self.node.close()

    def remote_path(self):
        paths = self.remotepaths
        if isinstance(self.remotepaths, str):
            paths = [ paths ]
        return "remote path {}".format(paths[0]) \
            if len(paths) == 1 \
               else "{} remote path(s) starting with {}"\
                   .format(len(self.remotepaths), self.remotepaths[0])

    def details(self):
        return "collect {}:{} into {}".\
            format(self.node.user_host(), self.remote_path(), self.localpath)

    def default_label(self):
        return self.details()
        
class SshJobPusher(AbstractJob):
    """
    Put local files onto target node
    """

    def __init__(self, node, localpaths, remotepath,
                 # set to False if not set explicitly here
                 forever = None,
                 # set to True if not set explicitly here
                 critical = None,
                 # asyncssh's SFTP client get option
                 preserve = False, recurse = False, follow_symlinks = False,
                 # this goes to AbstractJob
                 *args, **kwds):
        self.node = node
        self.localpaths = localpaths
        self.remotepath = remotepath
        # set defaults to pass to upper level
        forever = forever if forever is not None else False
        critical = critical if critical is not None else True
        self.preserve = preserve
        self.recurse = recurse
        self.follow_symlinks = follow_symlinks
        AbstractJob.__init__(self, forever=forever, critical=critical, *args, **kwds)

    async def co_run(self):
        await self.node.put_file_s(self.localpaths, self.remotepath,
                                   preserve = self.preserve,
                                   recurse = self.recurse,
                                   follow_symlinks = self.follow_symlinks)                                   

    async def co_shutdown(self):
        await self.node.close()    

    def local_path(self):
        paths = self.localpaths
        if isinstance(self.localpaths, str):
            paths = [ paths ]
        return "local path {}".format(paths[0]) \
            if len(paths) == 1 \
               else "{} local path(s) starting with {}"\
                   .format(len(self.localpaths), self.localpaths[0])

    def details(self):
        return "push {} onto {}:{}".\
            format(self.local_path(), self.node.user_host(), self.remotepath)
        
        
    def default_label(self):
        return self.details()

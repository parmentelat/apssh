import psutil

#class PsTree:
#
#    def __init__(self, pid):
#        self.pid = pid
#        self.children = []
#    def add_child(self, node):
#        self.children.append(node)

class ProcessMonitor:
    """
    Memorize the state of processes at one point in time
    and then can cmopute differences in terms of new/exited processes
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """
        Adjust to currently running processes
        """
        self.pids = set(psutil.pids())
        self.procs = [psutil.Process(pid) for pid in self.pids]

    def difference(self):
        """
        find out new/exited processes since last reset(),
        store result as set of ints in

        self.olds
        self.news

        """
        pids_now = set(psutil.pids())
#        procs_now = [psutil.Process(pid) for pid in self.pids]

        self.news = pids_now - self.pids
        self.olds = self.pids - pids_now

    def ssh_family(self):
        """
        returns a set of psutil.Process objects
        that are descendant of the main sshd service
        """
        relevant = set()
        # find unique sshd instance that has ppid 1
        for proc in self.procs:
            if 'sshd' in proc.name() and proc.ppid() == 1:
                relevant.add(proc.pid)

        changes = True
        while changes:
            changes = False
            for proc in self.procs:
                if proc.pid in relevant:
                    continue
                if proc.ppid() in relevant:
                    changes=True
                    relevant.add(proc.pid)

        print(relevant)

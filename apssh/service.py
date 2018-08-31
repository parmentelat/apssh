import asynciojobs
from apssh import SshJob, Run
import random

class Service:
    @staticmethod
    def _random_id():
        """
        Generate a random string to avoid conflicting names
        on the remote host
        """
        return "".join(random.choice('abcdefghijklmnopqrstuvwxyz')
                       for i in range(8))

    def __init__(self, id=None, tty=False, type='simple', command=None):
        self.tty = tty
        self.type = type
        if command is None:
            print("WARNING: Service require a command")
        self.command = command
        self.id = (self._random_id() if not id else str(id) +
                   "-"+self._random_id())
    def _get_service_command(self):
        return "systemd-run {}".format(("-t" if self.tty else ""))\
                + " --service-type={} --unit={}".format(self.type, self.id)\
                + " {}".format(self.command)

    def start_job(self, node, required=None, verbose=None,
                  forever=None, critical=None,
                  job_label=None, command_label=None):

        return SshJob(node=node,
                      required=required,
                      verbose=verbose,
                      forever=forever,
                      critical=critical,
                      label=job_label,
                      command=Run(self._get_service_command(),
                                  label=command_label)
                      )

    def stop_job(self, node, required=None, verbose=None,
                 forever=None, critical=None,
                 job_label=None, command_label=None):

        return SshJob(node=node,
                      required=required,
                      verbose=verbose,
                      forever=forever,
                      critical=critical,
                      label=job_label,
                      command=Run("systemctl stop {}".format(self.id),
                                  label=command_label)
                      )

    def start_command(self, label=None):
        return Run(self._get_service_command(), label=label)

    def stop_command(self, label=None):
        return Run("systemctl stop {}".format(self.id), label=label)

    def start_scheduler(self, node, required=None, verbose=None,
                        forever=None, critical=None,
                        job_label=None, command_label=None,
                        scheduler_label=None):

        job = self.start_job(node,
                             verbose=verbose,
                             forever=forever, critical=critical,
                             job_label=job_label, command_label=command_label)
        return asynciojobs.Scheduler(job, required=required, forever=forever,
                                     critical=critical,
                                     label=scheduler_label)

    def stop_scheduler(self, node, required=None , verbose=None,
                       forever=None, critical=None,
                       job_label=None, command_label=None,
                       scheduler_label=None):

        job = self.stop_job(node,
                            verbose=verbose,
                            forever=forever, critical=critical,
                            job_label=job_label, command_label=command_label)
        return asynciojobs.Scheduler(job, required=required, forever=forever,
                                     critical=critical,
                                     label=scheduler_label)

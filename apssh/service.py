"""
The service module defines the Service helper class.
"""

# pylint: disable=r1705

import random

from .commands import Run

class Service:
    """
    The Service class is a helper class, that allows to deal with services
    that an experiment scheduler needs to start and stop over the course
    of its execution. It leverages ``systemd-run``, which thus needs
    to be available on the remote box.

    Typical examples include starting and stopping a netcat server,
    or a tcpdump session.

    A Service instance is then able to generate a Command instance for
    starting or stopping the service, that should be inserted in an SshJob,
    just like e.g. a usual Run instance.

    Parameters:
      command(str): the command to start the service
      service_id(str): a unique id used to refer to that particular service;
        the class always add a randomly generated salt to the (optional)
        user-provided id.
      tty(bool): some services require a pseudo-tty to work properly
      systemd_type(str): a systemd service unit can have several values
        for its ``type`` setting, depending on the forking strategy implemented
        in the main command. The default used in Service is ``simple``,
        which is correct for a command that hangs (does not fork
        or go in the background). If on the contrary the command already
        handles forking, then it may be appropriate to use the ``forking``
        systemd type instead. Refer to systemd documentation for more details,
        at
        https://www.freedesktop.org/software/systemd/man/systemd.service.html#Type=
      environ: a dictionary that defines additional environment variables
        to be made visible to the running service. In contrast with what happens
        with regular `Run` commands, processes forked by systemd have a very
        limited set of environment variables defined - typically only
        ``LANG`` and ``PATH``. If your program rely on, for example,
        the ``USER`` variable to be defined as well, you may specify it here,
        for example ``environ={'USER': 'root'}``.

    """
    def __init__(self, command, *,
                 service_id=None,
                 tty=False,
                 systemd_type='simple',
                 environ=None,
                 verbose=False,
                 ):
        self.command = command
        self.tty = tty
        self.systemd_type = systemd_type
        self.service_id = service_id
        self.salt = self._salt()
        self.full_id = self.salt if not service_id \
                       else "{}-{}".format(service_id, self.salt)
        self.environ = environ if environ else {}
        self.verbose = verbose

    @staticmethod
    def _salt():
        """
        Generate a random string to avoid conflicting names
        on the remote host
        """
        return "".join(random.choice('abcdefghijklmnopqrstuvwxyz')
                       for i in range(8))

    def _label(self):
        if self.service_id:
            return "{}[-{}]".format(self.service_id, self.salt)
        else:
            return self.salt


    def _start(self):
        tty_option = "" if not self.tty else "--pty"
        command = ""
        if self.environ:
            defines = (" ".join("{}='{}'".format(var, value)
                                for var, value in self.environ.items()))
            command = ("systemctl set-environment {} ;"
                       .format(defines))

        command += ("systemd-run {} --unit={} --service-type={} {}"
                    .format(tty_option, self.full_id,
                            self.systemd_type, self.command))
        return command

    def _manage(self, subcommand):
        """
        subcommand is sent to systemctl, be it status or stop
        """
        return "systemctl {} {}"\
               .format(subcommand, self.full_id)

    def mode_label(self, mode, user_defined):
        if user_defined:
            return user_defined
        if not self.verbose:
            return "Service: {} {}".format(mode, self._label())
        # verbose: show command
        return "Serv: {} {} ➝ {}".format(mode, self._label(), self.command)

    def start_command(self, *, label=None, **kwds):
        """
        Returns:
          a Run instance suitable to be inserted in a SshJob object
        """
        label = self.mode_label("start", label)
        return Run(self._start(), label=label, **kwds)

    def stop_command(self, *, label=None, **kwds):
        """
        Returns:
          a Run instance suitable to be inserted in a SshJob object
        """
        label = self.mode_label("stop", label)
        return Run(self._manage('stop'), label=label, **kwds)

    def status_command(self, *, output=None, label=None, **kwds):
        """
        Returns:
          a Run instance suitable to be inserted in a SshJob object
        """
        command = self._manage('status')
        if output:
            command += " > {}".format(output)
        label = self.mode_label("status", label)
        return Run(command, label=label, **kwds)

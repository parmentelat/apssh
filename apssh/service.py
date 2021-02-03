"""
The service module defines the ``Service`` helper class.
"""

# pylint: disable=r1705, r0902

import random

from .commands import Run
from .deferred import Deferred

class Service:
    """
    The ``Service`` class is a helper class, that allows to deal with services
    that an experiment scheduler needs to start and stop over the course
    of its execution. It leverages ``systemd-run``, which thus needs
    to be available on the remote box.

    Typical examples include starting and stopping a netcat server,
    or a tcpdump session.

    A ``Service`` instance is then able to generate a Command instance for
    starting or stopping the service, that should be inserted in an SshJob,
    just like e.g. a usual Run instance.

    Parameters:
      command(str): the command to start the service;
        a ``Deferred`` instance is acceptable too
      service_id(str): this mandatory id is passed to ``systemd-run``
        to monitor the associated transient service;
        should be unique on a given host,
        in particular so that ``reset-failed`` can work reliably
      tty(bool): some services require a pseudo-tty to work properly
      systemd_type(str): a systemd service unit can have several values
        for its ``type`` setting, depending on the forking strategy implemented
        in the main command. The default used in ``Service`` is ``simple``,
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
        for example ``environ={'USER': 'root'}``
      stop_if_running: by default, prior to starting the service using systemd-run,
        ``start_command`` will ensure that no service of that name is currently
        running; this is especially useful when running the same experiment
        over and over, if you cannot be sure that your experiment code properly
        stops that service.
        Setting this attribute to ``False`` prevents this behaviour, and in
        that case the `start_command` will issue a mere invokation of
        ``systemd-run``.


    Example:
      To start a remote service that triggers a tcpdump session::

        service = Service(
            "tcpdump -i eth0 -w /root/ethernet.pcap",
            service_id='tcpdump',
            tty=True)

        SshJob(
            remotenode,
            commands=[
                Run(service.start_command()),
            ],
            scheduler=scheduler,
        )

        # and down the road when you're done

        SshJob(
            remotenode,
            commands=[
                Run(service.stop_command()),
            ],
            scheduler=scheduler,
        )

    """
    def __init__(self, command, *, service_id,
                 tty=False,
                 systemd_type='simple',
                 environ=None,
                 stop_if_running=True,
                 verbose=False):
        self.command = command
        self.service_id = service_id
        self.tty = tty
        self.systemd_type = systemd_type
        self.environ = environ if environ else {}
        self.stop_if_running = stop_if_running
        self.verbose = verbose


    def _start(self):
        # the -t option is a.k.a. --pty but on ubuntu-16.04 at least
        # the long version is broken
        commands = []
        if self.stop_if_running:
            # stop if running
            is_active = self._manage("is-active", trash_output=True)
            stop = self._manage("stop")
            commands.append(f"{is_active} && {stop}")
            # reset-failed
            commands.append(self._manage("reset-failed", trash_output=True))

        # it seems safer to avoid affecting global state
        # so we avoid systemctl set-environment
        # and use --setenv option instead
        environ_options = " ".join(
                f"--setenv {var}='{value}'" for var, value in self.environ.items()
            )

        tty_option = "" if not self.tty else "--pty"
        commands.append(f"systemd-run {tty_option}"
                        f" {environ_options}"
                        f" --unit={self.service_id}"
                        f" --service-type={self.systemd_type}"
                        f" {self.command}")

        # support deferred evaluation
        # here we need to preserve the type of self.command
        intermediate = " ; ".join(commands)
        if isinstance(self.command, Deferred):
            # create a deferred with the same variables environment
            return self.command.dup_from_string(intermediate)
        else:
            return intermediate


    def _manage(self, subcommand, trash_output=False):
        """
        subcommand is sent to systemctl, be it status or stop
        """
        trash_part = " >& /dev/null" if trash_output else ""
        return f"systemctl {subcommand} {self.service_id}{trash_part}"

    def _mode_label(self, mode, user_defined):
        if user_defined:
            return user_defined
        if mode != 'start' or not self.verbose:
            return f"Service: {mode} {self.service_id}"
        # start & verbose: show command
        multiline = self._start().replace(';', '\n')
        return fr"Service: {self.service_id}\n{multiline}"

    def start_command(self, *, label=None, **kwds):
        """
        Returns:
          a Run instance suitable to be inserted in a SshJob object
        """
        label = self._mode_label("start", label)
        return Run(self._start(), label=label, **kwds)

    def stop_command(self, *, label=None, **kwds):
        """
        Returns:
          a Run instance suitable to be inserted in a SshJob object
        """
        label = self._mode_label("stop", label)
        return Run(self._manage('stop'), label=label, **kwds)

    def status_command(self, *, output=None, label=None, **kwds):
        """
        Returns:
          a Run instance suitable to be inserted in a SshJob object
        """
        command = self._manage('status')
        if output:
            command += f" > {output}"
        label = self._mode_label("status", label)
        return Run(command, label=label, **kwds)

    # since : see journalctl options
    # e.g. since="10 seconds ago"
    def journal_command(self, *, label=None, since=None, **kwds):
        command = f"journalctl --unit {self.service_id}"
        if since:
            command += f' --since "{since}"'
        return Run(command, label=label, **kwds)

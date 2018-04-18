"""
the apssh package

https://github.com/parmentelat/apssh
http://apssh.readthedocs.io/

"""

from .version import __version__

# protect for install-time when dependencies are not yet installed
try:
    import asyncssh

    # basic tools to deal with keys
    from .keys import load_private_keys, load_agent_keys, import_private_key

    # basic ssh connections and sessions
    from .sshproxy import SshProxy

    # how to format outputs
    from .formatters import (
        RawFormatter, TerminalFormatter,
        ColonFormatter, TimeColonFormatter, CaptureFormatter
    )

    from .commands import Run, RunScript, RunString, Push, Pull

    # jobs for asynciojobs
    from .sshjob import SshJob, CommandFailedError

    # SshNode is just an SshProxy with a slightly different
    #  default for keys management
    # LocalNode is helpful to add local commands in a scenario
    from .nodes import SshNode, LocalNode
except Exception as exc:                                # pylint: disable=W0703
    print("Warning: could not import module asyncssh")

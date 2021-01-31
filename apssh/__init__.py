"""
the apssh package

https://github.com/parmentelat/apssh
http://apssh.readthedocs.io/

"""

from .version import __version__

# protect for install-time when dependencies are not yet installed
try:
    import asyncssh

except ModuleNotFoundError:
    print("WARNING: could not import asyncssh, required by apssh")

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

from .service import Service

from .topology import (
    close_ssh_in_scheduler, co_close_ssh_in_scheduler,
    topology_graph, topology_dot, topology_as_dotfile, topology_as_pngfile
)

from .deferred import (
    Variables, Deferred, Capture,
)
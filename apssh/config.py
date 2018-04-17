"""
default config for apssh
"""

# it's not desirable to change these names to uppercase
# pylint: disable=c0103, c0326

import os
import pwd
import time
from pathlib import Path

default_time_name = time.strftime("%Y-%m-%d@%H:%M")
default_username = pwd.getpwuid(os.getuid())[0]
default_timeout = 30
default_private_keys = (
    Path.home() / ".ssh/id_rsa",
    Path.home() / ".ssh/id_dsa",
)

local_config_dir = Path.home() / ".apssh"
# dont use expanduser as this is relative to a remote system
default_remote_workdir = ".apssh-remote"

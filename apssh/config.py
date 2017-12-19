import os
import pwd
import time
from pathlib import Path

default_time_name =             time.strftime("%Y-%m-%d@%H:%M")
default_username =              pwd.getpwuid(os.getuid())[0]
default_timeout =               30
default_private_keys =          (
    Path("~/.ssh/id_rsa").expanduser(),
    Path("~/.ssh/id_dsa").expanduser(),
)

local_config_dir =              Path("~/.apssh").expanduser()
# dont use expanduser as this is relative to a remote system
default_remote_workdir =        ".apssh-remote"

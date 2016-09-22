import os
import pwd
import time

default_time_name =             time.strftime("%Y-%m-%d@%H:%M")
default_username =              pwd.getpwuid(os.getuid())[0]
default_timeout =               30
default_private_keys =           os.path.expanduser("~/.ssh/id_rsa"), os.path.expanduser("~/.ssh/id_dsa"), 

# dont use expanduser as this is relative to a remote system
default_remote_workdir =        ".apssh"

import os
import time

default_time_name =             time.strftime("%Y-%m-%d@%H:%M")
default_username =              os.getlogin()
default_timeout =               30
default_private_key =           os.path.expanduser("~/.ssh/id_rsa")
# dont use expanduser as this is relative to a remote system
default_remote_workdir =        ".apssh"

# pylint: disable=c0111

import os
import subprocess
import platform
from pathlib import Path

import psutil


# environment
def localuser():
    return os.environ['LOGNAME']

def localhostname():
    command = "hostname"
    completed = subprocess.run(command, stdout=subprocess.PIPE)
    return (completed.stdout
            .decode(encoding='utf-8')
            .replace("\n", ""))


# shortcut to make png output
def produce_png(scheduler, name):
    dot = scheduler.graph()
    dot.format = 'png'

    tests_dir = Path('tests')
    if tests_dir.exists():
        actual_name = str(tests_dir / name)
    else:
        actual_name = name
    dot.render(actual_name)
    print(f"png file produced in {actual_name}{{,.png}}")


# process management
def pid_is_alive(pid):
    return psutil.pid_exists(pid)

def get_pid_from_apssh_file(filename):
    with Path(filename).open() as file:
        data = file.readline()
        try:
            ret = int(data)
        except ValueError:
            ret = -1
        return ret

def get_apssh_files_list(path):
    #path = path + ".apssh/apssh_spid_*"
    path += "/.apssh"
    pattern = "apssh_spid_*"

    return list(Path(path).glob(pattern))

def check_apssh_files_alive(file_list):
    alive = 0
    if len(file_list) > 0:
        for file in file_list:
            pid = get_pid_from_apssh_file(file)
            if pid_is_alive(pid):
                alive = alive + 1
    return alive

def count_ssh_connections_psutil(incoming:bool, outgoing:bool):
    connections = psutil.net_connections(kind="tcp4")
    count = 0
    for conn in connections:
        if conn.status == psutil.CONN_ESTABLISHED:
            if conn.laddr.ip == '127.0.0.1' and conn.raddr.ip == '127.0.0.1':
                if (incoming and conn.laddr.port == 22)\
                 or (outgoing and conn.raddr.port == 22):
                    count += 1
    return count
# ssh connections accounting
def count_ssh_connections(incoming:bool, outgoing:bool):
    """
    tool for counting open connections

    based on linux's 'ss' command for now
    """
    # False positive if there are outgoing or incomming connection from another
    # address than localhost
    if platform.system() != "Linux":
        raise ValueError(f"inspector works only on linux boxes")
    if not incoming and not outgoing:
        return 0
    filters = []
    if incoming:
        filters.append("sport = :ssh")
    if outgoing:
        filters.append("dport = :ssh")
    command = []
    command.append("ss")
    command += "-o state established".split()
    filter = "( " + " or ".join(filters) + " )"
    command.append(filter)
#    print(" ".join(command))
    completed = subprocess.run(command, stdout=subprocess.PIPE)
    count = 0
#    lines = completed.stdout.decode(encoding='utf8').split('\n')
    for line in completed.stdout.split(b"\n"):
        if not line or b"Netid" in line:
            continue
#        print(f"counting line {line}")
        count += 1
    return count

def incoming_connections():
    return count_ssh_connections_psutil(incoming=True, outgoing=False)

def outgoing_connections():
    return count_ssh_connections_psutil(outgoing=True, incoming=False)

def in_out_connections():
    return incoming_connections(), outgoing_connections()

def count_file_descriptors():
    process = psutil.Process(os.getpid())
    return process.num_fds()

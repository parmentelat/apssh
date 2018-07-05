# pylint: disable=c0111

import subprocess
import platform
from pathlib import Path

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


def count_ssh_connections(incoming:bool, outgoing:bool):

    """
    tool for counting open connections

    based on linux's 'ss' command for now
    """



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
    return count_ssh_connections(incoming=True, outgoing=False)

def outgoing_connections():
    return count_ssh_connections(outgoing=True, incoming=False)

def in_out_connections():
    return incoming_connections(), outgoing_connections()

if __name__ == '__main__':
    print(f"incoming {incoming_connections()}")
    print(f"outgoing {outgoing_connections()}")

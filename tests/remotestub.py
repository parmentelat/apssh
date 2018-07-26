#!/usr/bin/env python3

import time

def sleep(timeout):
    delay = int(timeout)
    time.sleep(delay)

if __name__ == '__main__':
    import sys
    fun_name, *args = sys.argv[1:]
    function = locals().get(fun_name, None)
    if not function:
        print(f"Unknown subcommand {fun_name}")
        exit(1)
    function(*args)

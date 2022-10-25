#!/usr/bin/env python3

import sys
import time

def sleep(timeout):
    delay = int(timeout)
    time.sleep(delay)

if __name__ == '__main__':
    fun_name, *args = sys.argv[1:]
    function = locals().get(fun_name, None)
    if not function:
        print(f"Unknown subcommand {fun_name}")
        sys.exit(1)
    function(*args)

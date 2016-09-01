import sys

def print_stderr(*args, **kwds):
    print(file=sys.stderr, *args, **kwds)



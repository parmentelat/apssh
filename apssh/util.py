"""
A set of helper functions for the apssh package
"""

import sys

def print_stderr(*args, **kwds):
    """
    A shorthand for ``print()`` but on standard error
    """
    print(file=sys.stderr, *args, **kwds)


def check_arg_type(instance, types, message):
    """
    The basic brick for explicit type checking in the apssh code

    raise ValueError if instance is not of any of the types

    types parameter is passed to isinstance, so may be either
    a class or a tuple of classes

    message would help identify the issue

    example:
      check_arg_type("foo.bar", SshProxy, "SshProxy.gateway")

    would result in a ValueError labelled with string

    >  SshProxy.gateway is expected to be an instance of SshProxy,
    >  got a str instead
    """
    if isinstance(instance, types):
        return

    # build a helpful error message

    # expected
    def atomic_typename(typeobj):                       # pylint: disable=c0111
        return typeobj.__name__
    if isinstance(types, tuple):
        msg_expected = " or ".join(atomic_typename(t) for t in types)
    else:
        msg_expected = atomic_typename(types)

    # received
    msg_received = atomic_typename(type(instance))

    # asembled
    msg_complete = (f"{message} is expected to be an instance of {msg_expected},"
                    f" got a {msg_received} instead")
    raise ValueError(msg_complete)

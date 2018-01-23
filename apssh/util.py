import sys


def print_stderr(*args, **kwds):
    print(file=sys.stderr, *args, **kwds)


def check_arg_type(instance, types, message):
    """
    raise ValueError of instance is not of any of the types

    types parameter is passed to isinstance, so may be either
    a class or a tuple of classes

    message would help identify the issue

    example
    check_arg_type("foo.bar", SshProxy, "SshProxy.gateway")
    would result in a ValueError labelled
    SshProxy.gateway is expected to be an instance of SshProxy, got a str instead
    """
    if isinstance(instance, types):
        return

    ### build a some helpful error message

    # expected
    def atomic_typename(typeobj):
        return typeobj.__name__
    if isinstance(types, tuple):
        msg_expected = " or ".join(atomic_typename(t) for t in types)
    else:
        msg_expected = atomic_typename(types)

    # received
    msg_received = atomic_typename(type(instance))

    # asembled
    msg_complete = "{} is expected to be an instance of {}, got a {} instead"\
                   .format(message, msg_expected, msg_received)
    raise ValueError(msg_complete)

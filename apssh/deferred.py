# typical usecase
#
# you want to write something like
# somevar=$(ssh nodename somecommand)
# ssh othernode othercommand $somevar
#
# as of 0.17.6, several obstacles are in the way
# * the capture mechanism that allows to mimick $(ssh blabla)
#   relies on using a formatter, which in turn is bound to a SshNode
#   and not a SshJob, which is a little unconvenient as it requires to
#   create artificial and volatile SshNode's and thus extra connections
# * because a Schduler is totally created before it gets to run anything,
#   creating a Run() instance from a string means that the string must be known
#   at sheduler-creation time, at which point we do not yet have the value of somevar
# * finally, we're going to need some mechanism to hol the content of such variables
#   because Python variables won't be able to do the job

class Variables(dict):
    """
    think of this class as a regular namespace, i.e. a set of associations
    variable -> value

    we cannot use the regular Python binding because at the time where
    a Scheduler gets built, those variables are not yet available

    and at the time where the command triggers
    """
    # support for the . notation
    def __getattr__(self, attr):
        return self.get(str(attr), '')

    def __setattr__(self, attr, value):
        self[attr] = value

class Deferred:
    """
    a Deferred object look a bit like a string template
    with variables enclosed in {}

    it can then be instantiated from a Variables object to replace the
    those fragments with the actual values found in the Variables object
    """
    def __init__(self, format, variables):
        self.format = format
        self.variables = variables

    def __str__(self):
        """
        replace expresions of the form {x} with the
        value of variable x as per the variables object
        """
        try:
            return self.format.format(**self.variables)
        except KeyError as exc:
            print("probably unknown variable in Deferred format")
            print(exc)
            raise

    def __repr__(self):
        return (f"Deferred with format {self.format} "
                "and variables {self.variables} ")

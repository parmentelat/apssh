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

from jinja2 import Template, DebugUndefined

class Variables(dict):
    """
    think of this class as a regular namespace, i.e. a set of associations
    variable -> value

    we cannot use the regular Python binding because at the time where
    a Scheduler gets built, those variables are not yet available

    so the Variables object collects values that are computed during
    a scheduler run
    """
    # support for the . notation
    def __getattr__(self, attr):
        return self.get(str(attr), '')

    def __setattr__(self, attr, value):
        self[attr] = value


class Deferred:
    """
    a Deferred object is made of 2 parts

    * a jinja template as a string that may contain variables or expressions
      enclosed in {}
    * a Variables instance, that collects values over time

    a Deferred object can be used to create instances
    of the Run class and its siblings;
    this is useful when the command contains a part
    that needs to be computed during the scenario

    Typically in a kubernetes-backed scenario,
    we often need to get node actual names
    from the k8s master
    """
    def __init__(self, template, variables):
        self.template = template
        self.variables = variables

    def __str__(self):
        """
        replace expresions of the form {x} with the
        value of variable x as per the variables object
        """
        template = Template(self.template, undefined=DebugUndefined)
        return template.render(**self.variables)

    def __repr__(self):
        return (f"Deferred with template {self.template} "
                f"and variables {self.variables} ")


# will become a dataclass
class Capture:
    """
    this class has no logic in itself, it is only a convenience so that
    one can specify where a Run command should store it's captured output

    for example a shell script like:
    
        foobar=$(ssh host1 some-command)
        ssh host2 other-command $foobar

    could be mimicked with (simplified version)

        env = Variables()
        Sequence(
            SshJob(host1node,
                   commands=Run("some-command",
                                capture=Capture('foobar', env)))
            SshJob(host2node,
                   commands=Run(Deferred("other-command {foo}", env)))
    """
    def __init__(self, varname: str, variables: Variables):
        self.varname = varname
        self.variables = variables

"""
Support for deferred evaluation; typical usecase is, you want to write something like::

    somevar=$(ssh nodename some-command)
    ssh othernode other-command $somevar

but because a Schduler is totally created before it gets to run anything, creating a
``Run()`` instance from a string means that the string must be known at sheduler-creation
time, at which point we do not yet have the value of somevar

that's where ``Deferred`` objects come in; they fill in for actual ``str`` objects, but
are actually templates that are rendered later on when the command is actually about to
trigger

typically in a kubernetes-backed scenario, we often need to get a pod's name by issuing an
ssh command to the master node, so this is not a static data that can be filled in the
code

"""

from jinja2 import Template, DebugUndefined

class Variables(dict):
    """
    think of this class as a regular namespace, i.e. a set of associations variable →
    value

    we cannot use the regular Python, binding because at the time where a Scheduler gets
    built, those variables are not yet available

    so the ``Variables`` object typically collects values that are computed during a
    scheduler run

    just like a JS object, a ``Variables`` object can be accessed through indexing or
    attributes all the same,

    so that::

        variables = Variables()
        variables.foo = 'bar'
        variables['bar'] = 'foo'
        variables.foo == variables['foo']  # True
        variables.var == variables['bar']  # True

    it is common to create a single ``Variables`` environment for a ``Scheduler`` run;
    variables inside the environment are often set by creating ``Run``-like objects with a
    ``Capture`` instance that specifies in what variable the result should end up
    """
    # support for the . notation
    def __getattr__(self, attr):
        return self.get(str(attr), '')

    def __setattr__(self, attr, value):
        self[attr] = value


class Deferred:
    """
    the ``Deferred`` class is the trick that lets you introduce what we call
    deferred evaluation in a scenario; main use case being when you run a remote
    command to compute something, that in turn is used later on by another
    Run or Service object; except that, because the scheduler and its jobs/commands
    pieces are created before it gets run, you cannot compute all the details right away,
    you need to have some parts replaces later on - that is, deferred

    Parameters:
      template(str): a Jinja template as a string, that may contain variables
        or expressions enclosed in ``{{}}``
      variables(Variables): an environment object that will collect values over time,
        so that variables in ``{{}}`` can be expansed when the time comes

    a ``Deferred`` object can be used to create instances
    of the ``Run`` class and its siblings, or of the ``Service`` class;
    this is useful when the command contains a part
    that needs to be computed during the scenario

    .. warning:: **beware of f-strings !**

       since Jinja templates use double brackets
       as delimiters for expressions, it is probably unwise to create a template
       from an f-string, or if you do you will have to insert variable inside
       quadruple brackets like so `{{{{varname}}}}`, so that after f-string evaluation
       a double bracket remains.
    """
    def __init__(self, template, variables):
        self.template = template
        self.variables = variables

    def __str__(self):
        """
        replace expresions of the form {x} with the
        value of variable x as per the variables object

        if undefined variables are used, the {{thing}} remains
        this is useful in particular in the context of graphic output
        which is mostly done before the scenario gets run, and so no variable
        are known at that point
        """
        template = Template(self.template, undefined=DebugUndefined)
        return template.render(**self.variables)

    def __repr__(self):
        return (f"Deferred with template {self.template} "
                f"and variables {self.variables} ")

    def replace(self, old, new):

        # NOTE: this method is **not** meant to be called explicitly
        #
        # it is there only because other parts of the code, in service.py notably,
        # do operations on commands expecting str objects, so they occasionnaly call
        # service.command.replace(old, new)
        #
        # this is **not** what actually performs expansion of {{}}
        # expressions in the template

        return Deferred(self.template.replace(old, new), self.variables)

    def dup_from_string(self, new_template):
        """
        Create a new ``Deferred`` object on the same ``Variables`` environment,
        but with a different template.
        """
        return Deferred(new_template, self.variables)


# will become a dataclass
class Capture:
    """
    this class has no logic in itself, it is only a convenience so that
    one can specify where a Run command should store it's captured output

    for example a shell script like::

        somevar=$(ssh nodename some-command)
        ssh othernode other-command $somevar

    could be mimicked with (simplified version)::

        env = Variables()
        Sequence(
            SshJob(node_obj,
                   # the output of this command ends up
                   # as the 'foobar' variable in env
                   commands=Run("some-command",
                                capture=Capture('somevar', env)))
            SshJob(other_node_obj,
                   # which we use here inside a jinja template
                   commands=Run(Deferred("other-command {{somevar}}", env)))
    """
    def __init__(self, varname: str, variables: Variables):
        self.varname = varname
        self.variables = variables

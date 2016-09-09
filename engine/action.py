import asyncio

debug = True

# my first inclination had been to specialize asyncio.Task
# it does not work well though, because you want to model
# dependencies **before** anything starts, of course
# but in asyncio, creating a Task object implies scheduling that for execution

# so, let's have it the other way around
# what we need is a way to attach our own Action instances to the Task (and back)
# classes right after Task creation, so that
# (*) once asyncio.wait is done, we can easily find out wich Actions are done or pending
# (*) from one Action, easily know what its status is by lloing into its Task obj
#     (if already started)

# Engine == graph
# Action == node

class Action:
    """
    Action is a virtual class:

    (*) it offers some very basic graph-related features to model requirements
        a la makefile
    (*) its subclasses are expected to implement a `corun()` method 
        that specifies the actual behaviour as a coroutine

    It's mostly a companion class to the Engine class, that does the heavy lifting
    """

    def __init__(self, label="[undefined_label]"):
        self.label = label 
        # list of Action objects that need to be completed before we can start this one
        self.required = []
        # once submitted in the asyncio loop/scheduler, the `corun()` gets embedded in a 
        # Task object, that is our handle when talking to asyncio.wait
        self._task = None
        # ==== fields for our friend Engine 
        # this is for graph browsing algos
        self._mark = None
        # the reverse of required
        self._successors = []

    def __repr__(self):
        info = "<Action `{}'".format(self.label)
        if self.required:
            info += " - [requires " + " ".join(["[{}]".format(a.label) for a in self.required]) + "]"
        if not self._task:
            info += " IDLE"
        else:
            info += " {}".format(self._task._state.lower())
        if self.is_done():
            info += " -> {}".format(self._task._result)
        if self._successors:
            info += " {} successor(s)".format(len(self._successors))
        info += ">"
        return info
    
    def requires(self, *actions):
        self.required += actions
        self.required = list(set(self.required))

    def is_started(self):
        return self._task is not None
    def is_done(self):
        return self._task and self._task._state == asyncio.futures._FINISHED
    def just_started(self, task):
        self._task = task

    async def corun(self):
        print("Action.corun() needs to be implemented on class {}"
              .format(self.__class__.__name__))



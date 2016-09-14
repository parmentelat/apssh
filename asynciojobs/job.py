import asyncio

debug = False
#debug = True

# my first inclination had been to specialize asyncio.Task
# it does not work well though, because you want to model
# dependencies **before** anything starts, of course
# but in asyncio, creating a Task object implies scheduling that for execution

# so, let's have it the other way around
# what we need is a way to attach our own Job instances to the Task (and back)
# classes right after Task creation, so that
# (*) once asyncio.wait is done, we can easily find out wich Jobs are done or pending
# (*) from one Job, easily know what its status is by lloing into its Task obj
#     (if already started)

# Engine == graph
# Job == node

class AbstractJob:
    """
    AbstractJob is a virtual class:

    (*) it offers some very basic graph-related features to model requirements
        a la makefile
    (*) its subclasses are expected to implement a `co_run()` method 
        that specifies the actual behaviour as a coroutine

    Can be created with 
    (*) boolean flag 'forever', if set, means the job is not returning at all and runs forever
        in this case Engine.orchestrate will not wait for that job, and will terminate it once all
        the regular i.e. not-forever jobs are done
    (*) an optional label - for convenience only

    It's mostly a companion class to the Engine class, that does the heavy lifting
    """

    def __init__(self, forever, label, critical=None):
        if label is None:
            label = "NOLABEL"
        self.label = label
        self.forever = forever
        self.critical = critical
        # list of Job objects that need to be completed before we can start this one
        self.required = set()
        # once submitted in the asyncio loop/scheduler, the `co_run()` gets embedded in a 
        # Task object, that is our handle when talking to asyncio.wait
        self._task = None
        # ==== fields for our friend Engine 
        # this is for graph browsing algos
        self._mark = None
        # the reverse of required
        self._successors = set()

    def __repr__(self):
        info = "<Job `{}'".format(self.label)
        ### outline forever jobs
        if self.forever:
            info += "[∞]"
        ### show info - IDLE means not started at all
        if not self._task:
            info += " UNSCHED"
        else:
            info += " {}".format(self._task._state.lower())
            ### if it has returned, show result
        if self.is_done():
            info += " -> {}".format(self.result())
        exception = self.raised_exception()
        if exception:
            info += " !!{}:{}!!".format(type(exception).__name__, exception)
        ### show dependencies in both directions
        if self.required:
            info += " - requires:{" + " ".join(["[{}]".format(a.label) for a in self.required]) + "}"
        if self._successors:
            info += " - allows: {" + " ".join(["[{}]".format(a.label) for a in self._successors]) + "}"
        info += ">"
        return info
    
    def requires(self, *jobs):
        self.required.update(jobs)

    def is_started(self):
        return self._task is not None
    def is_done(self):
        return self._task is not None and self._task._state == asyncio.futures._FINISHED
    def raised_exception(self):
        """returns an exception if applicable, or None"""
        return self._task is not None and self._task._exception

    def is_critical(self, engine):
        """
        If critical is set locally, use that
        otherwise the engine tells the default
        """
        if self.critical is not None:
            return self.critical
        return engine.is_critical()

    def result(self):
        if not self.is_done():
            raise ValueError("job not finished")
        return self._task._result

    async def co_run(self):
        """
        abstract virtual - needs to be implemented
        """
        print("AbstractJob.co_run() needs to be implemented on class {}"
              .format(self.__class__.__name__))

    async def co_shutdown(self):
        """
        abstract virtual - needs to be implemented
        """
        print("AbstractJob.co_shutdown() needs to be implemented on class {}"
              .format(self.__class__.__name__))

    def standalone_run(self):
        """
        Just run this one job on its own - useful for debugging
        the internals of that job, e.g. for checking for gross mistakes
        and other exceptions
        """
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.co_run())


####################
class Job(AbstractJob):

    """
    Most mundane form is to provide a coroutine yourself
    """
    
    def __init__(self, coro, forever=False, label=None, *args, **kwds):
        self.coro = coro
        AbstractJob.__init__(self, forever=forever, label=label, *args, **kwds)

    async def co_run(self):
        result = await self.coro
        return result

    async def co_shutdown(self):
        pass

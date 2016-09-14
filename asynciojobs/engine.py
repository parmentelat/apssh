#!/usr/bin/env python3

import time
import asyncio

class Engine:
    """
    An Engine instance works on a set of Job objects

    It will orchestrate them until they are all complete,
    starting with the ones that have no requirements, 
    and then starting the othe ones as their requirements are satisfied

    Running a Job means executing its co_run() method, which must be a coroutine

    As of this rough/early implementation: 
    (*) the result of `co_run` is not yet taken into account to implement some
        logic about how the overall job should behave. Instead the results of individual
        jobs can be retrieved individually when thei state is finished

    (*) exceptions are still in the work and probably not too well handled
        it's not clear yet what should happen if co_run raises an exception
    """

    default_critical = False

    def __init__(self,  *jobs, critical=None, debug=False):
        self.jobs = jobs
        self.jobs = list(set(self.jobs))
        if critical is None:
            critical = self.default_critical
        self.critical = critical
        self.debug = debug

    def add(self, jobs):
        self.jobs += jobs
        self.jobs = list(set(self.jobs))

    def list(self):
        """
        print internal jobs as sorted in self.jobs
        mostly useful after .rain_check()
        """
        for i, job in enumerate(self.jobs):
            print(i, job)
        
    def is_critical(self):
        return self.critical

    def _reset_marks(self):
        """
        reset Job._mark on all jobs
        """
        for job in self.jobs:
            job._mark = None

    def _reset_tasks(self):
        """
        In case one tries to run the same engine twice
        """
        for job in self.jobs:
            job._task = None

    def _backlinks(self):
        """
        initialize Job._successors on all jobs
        as the reverse of Job.required
        """
        for job in self.jobs:
            job._successors = []
        for job in self.jobs:
            for req in job.required:
                req._successors.append(job)

    def rain_check(self):
        """
        performs minimum sanity check

        NOTE: the purpose of this is primarily to check for cycles
        it's not embedded in orchestrate because it's not strictly necessary
        but it's safer to run this before calling orchestrate if one wants 
        to type-check the jobs dependency graph early on

        SIDE EFFECT:
        re-order self.jobs so that the free jobs a.k.a. entry points
        i.e. jobs with no requirements, show up first
        more generally, if a requires b, a will show up before b in self.jobs

        RETURN:
        a boolean that is True if the topology looks clear 
        """
        # clear marks
        self._reset_marks()
        # reset self.jobs, but of course set aside
        saved_jobs = self.jobs
        self.jobs = []
        # mainloop
        while True:
            # detect a fixed point 
            changed = False
            # loop on unfinished business
            for job in saved_jobs:
                # if there's no requirement (first pass),
                # or later on if all requirements have already been marked,
                # then we can mark this one
                has_unmarked_requirements = False
                for required_job in job.required:
                    if required_job._mark is None:
                        has_unmarked_requirements = True
                if not has_unmarked_requirements:
                    if self.debug:
                        print("rain_check: marking {}".format(job))
                    job._mark = True
                    self.jobs.append(job)
                    saved_jobs.remove(job)
                    changed = True
            if not saved_jobs:
                # we're done
                break
            if not changed:
                if self.debug:
                    print("rain_check: loop makes no progress - we have a problem")
                # restore list of jobs
                self.jobs += saved_jobs
                # this is wrong
                return False
        # if we still have jobs here it's not quite good either
        if saved_jobs:
            if self.debug:
                print("rain_check: we have {} jobs still in the pool and can't reach them from free jobs")
            return False
        return True

    def ensure_future(self, job, loop):
        """
        this is the hook that lets us make sure the created Task object have a 
        backlink pointer to its correponding job
        """
        task = asyncio.ensure_future(job.co_run(), loop=loop)
        if self.debug:
            print("scheduling job {}".format(job.label))
        # create references back and forth between Job and asyncio.Task
        task._job = job
        job._task = task
        return task

    def mark_beginning(self, timeout):
        """
        Called once at the beginning of orchestrate, this method computes the absolute
        expiration date when a timeout is defined. 
        """
        if timeout is None:
            self.expiration = None
        else:
            self.expiration = time.time() + timeout

    def remaining_timeout(self):
        """
        Called each time orchestrate is about to call asyncio.wait(), this method
        computes the timeout argument for wait - or None if orchestrate had no timeout
        """
        if self.expiration is None:
            return None
        else:
            return self.expiration - time.time()

    async def _tidy_tasks(self, pending):
        """
        Once orchestrate is done with its job, in order to tidy up the underlying 
        Task objects that have not completed, it is necessary to cancel them and wait for them
        according to the context, this can be with forever tasks, or because a timeout has occured
        """
        if pending:
            for task in pending:
                task.cancel()
            # wait for the forever tasks for a clean exit
            # don't bother to set a timeout, as this is expected to be immediate
            # since all tasks are canceled
            await asyncio.wait(pending)
        
    async def _tidy_task_exception(self, task):
        """
        Similar but in order to clear the exception, we need to run gather() instead
        """
        task.cancel()
        # don't bother to set a timeout, as this is expected to be immediate
        # since all tasks are canceled
        await asyncio.gather(task, return_exceptions=True)
        
    def orchestrate(self, loop=None, *args, **kwds):
        if loop is None:
            loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.co_orchestrate(loop=loop, *args, **kwds))

    async def co_orchestrate(self, loop=None, timeout=None):
        """
        the primary entry point for running an ordered set of jobs
        """
        if loop is None:
            loop = asyncio.get_event_loop()
        # initialize backlinks - i.e. _successors is the reverse of required
        self._backlinks()
        # clear any Task instance
        self._reset_tasks()

        self.mark_beginning(timeout)

        # how many jobs do we expect to complete: the ones that don't run forever
        nb_jobs_finite = len([j for j in self.jobs if not j.forever])
        # the other ones
        nb_jobs_forever = len(self.jobs) - nb_jobs_finite
        # count how many jobs have completed
        nb_jobs_done = 0

        # start with the free jobs
        entry_jobs = [ job for job in self.jobs if not job.required ]

        if not entry_jobs:
            raise ValueError("No entry points found - cannot orchestrate")
        
        pending = [ self.ensure_future(job, loop=loop)
                    for job in entry_jobs ]
        
        while True:
            done, pending \
                = await asyncio.wait(pending,
                                     timeout = self.remaining_timeout(),
                                     return_when = asyncio.FIRST_COMPLETED)

            if self.debug:
                print("orchestrate: {} iteration {} / {} - {} done and {} pending"
                      .format(4*'-', nb_jobs_done, nb_jobs_finite,
                              len(done), len(pending)))
            # nominally we have exactly one item in done
            # it looks like the only condition where we have nothing in done is
            # because a timeout occurred
            if not done or len(done) == 0:
                if self.debug:
                    print("orchestrate: TIMEOUT occurred")
                # clean up
                await self._tidy_tasks(pending)
                return False
            # surprisingly I can see cases where done has more than one entry
            # typically when 2 jobs have very similar durations
            if self.debug:
                print("JOBS DONE = {}".format(done))

            # are we done ?
            nb_jobs_done += len(done)
            if nb_jobs_done == nb_jobs_finite:
                if self.debug:
                    print("orchestrate: {} CLEANING UP at iteration {} / {}"
                          .format(4*'-', nb_jobs_done, nb_jobs_finite))
                assert len(pending) == nb_jobs_forever
                await self._tidy_tasks(pending)
                return True

            # exceptions need to be cleaned up 
            for done_task in done:
                done_job = done_task._job
                # do we have at least one critical job with an exception ?
                critical = False
                if done_job.raised_exception():
                    critical = critical or done_job.is_critical(self)
                    if self.debug:
                        print("orchestrate: EXCEPTION occurred - critical = {}".format(critical))
                    # clear the exception
                    await self._tidy_task_exception(done_task)
                if critical:
                    await self._tidy_tasks(pending)
                    return False

            # go on : find out the jobs that can be added to the mix
            # only consider the ones that are right behind any of the the jobs that just finished
            possible_next_jobs = []
            for done_task in done:
                possible_next_jobs += done_task._job._successors
            # remove duplicates
            possible_next_jobs = list(set(possible_next_jobs))
            if self.debug:
                print("possible ->", len(possible_next_jobs))
                for a in possible_next_jobs:
                    print(a)

            # find out which ones really can be added
            added = 0
            for candidate_next in possible_next_jobs:
                # do not add an job twice
                if candidate_next.is_started():
                    continue
                # we can start only if all requirements are satisfied
                # at this point entry points have is_started() -> return True so
                # they won't run this code
                requirements_ok = True
                for req in candidate_next.required:
                    if not req.is_done():
                        requirements_ok = False
                if requirements_ok:
                    pending.add(self.ensure_future(candidate_next, loop=loop))
                    added += 1

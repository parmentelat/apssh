#!/usr/bin/env python3

import asyncio

debug = False
#debug = True

class Engine:
    """
    An Engine instance works on a set of Job objects

    It will orchestrate them until they are all complete,
    starting with the ones that have no requirements, 
    and then starting the othe ones as their requirements are satisfied

    Running a Job means executing its corun() method, which must be a coroutine

    As of this rough/early implementation: 
    (*) the result of `corun` is not yet taken into account to implement some
        logic about how the overall job should behave

    (*) exceptions are probably not well handled so it's not clear what should happen
        if corun raises an exception
    
    """

    def __init__(self, *jobs):
        self.jobs = jobs
        self.jobs = list(set(self.jobs))

    def add(self, jobs):
        self.jobs += jobs
        self.jobs = list(set(self.jobs))

    def list(self):
        """
        print internal jobs as sorted in self.jobs
        mostly useful after .order()
        """
        for job in self.jobs:
            print(job)
        
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

    def order(self):
        """
        performs minimum sanity check -- raise ValueError if the topology cannot be handled

        NOTE: the purpose of this is primarily to check for cycles
        it's not embedded in orchestrate because it's not strictly necessary
        but it's safer to do so before calling orchestrate if one wants 
        to type-check the jobs dependency graph early on

        SIDE EFFECT: 
        re-order self.jobs so that the free jobs a.k.a. entry points
        i.e. jobs with no requirements, show up first

        RETURN:
        None, or an exception gets fired
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
                    if debug: print("order: marking {}".format(job.label))
                    job._mark = True
                    self.jobs.append(job)
                    saved_jobs.remove(job)
                    changed = True
            if not saved_jobs:
                # we're done
                break
            if not changed:
                if debug: print("order: loop makes no progress - we have a problem")
                raise ValueError("only acyclic graphs are supported")
        # if we still have jobs here it's not quite good either
        if saved_jobs:
            print("order: we have {} jobs still in the pool and can't reach them from free jobs")
            raise ValueError("cyclic graph")

    @staticmethod
    def ensure_future(job, loop):
        """
        this is the hook that lets us make sure the created Task object have a 
        backlink pointer to its correponding job
        """
        task = asyncio.ensure_future(job.corun(), loop=loop)
        if debug: print("scheduling job {}".format(job.label))
        task._job = job
        job._task = task
        return task

    def orchestrate(self, loop=None):
        """
        the primary entry point for running an ordered set of jobs
        """
        if loop is None:
            loop = asyncio.get_event_loop()
        # initialize
        self._backlinks()
        self._reset_tasks()

        # how many jobs do we expect to complete: the ones that don't run forever
        nb_jobs_finite = len([j for j in self.jobs if not j.forever])
        nb_jobs_forever = len(self.jobs) - nb_jobs_finite
        # count how many jobs have completed
        nb_jobs_done = 0

        # start with the free jobs
        entry_jobs = [ job for job in self.jobs if not job.required ]

        if not entry_jobs:
            raise ValueError("No entry points found - cannot orchestrate")
        
        pending = [ Engine.ensure_future(job, loop=loop)
                    for job in entry_jobs ]
        
        while True:
            if debug: print("orchestrate: {} iteration {} / {}"
                            .format(4*'-', nb_jobs_done, nb_jobs_finite))
            done, pending \
                = loop.run_until_complete(asyncio.wait(pending,
                                                       return_when = asyncio.FIRST_COMPLETED))

            # nominally we have exactly one item in done
            if not done or len(done) != 1:
                print("NOT GOOD - we're stalled ...")
                return False
            done_job = list(done)[0]._job
            if debug:
                print("JOB DONE = {}".format(done_job.label))

            # are we done ?
            nb_jobs_done += len(done)
            if nb_jobs_done == nb_jobs_finite:
                if debug: print("orchestrate: {} CLEANING UP at iteration {} / {}"
                                .format(4*'-', nb_jobs_done, nb_jobs_finite))
                assert len(pending) == nb_jobs_forever
                if pending:
                    for task in pending:
                        task.cancel()
                    # epilogue : wait for the forever tasks for a clean exit
                    done, pending \
                        = loop.run_until_complete(asyncio.wait(pending,
                                                               return_when = asyncio.FIRST_COMPLETED))
                    
                return True

            # go on : find out the jobs that can be added to the mix
            # only consider the ones that are right behind the job that just finished
            possible_next_jobs = done_job._successors
            if debug:
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
                    pending.add(Engine.ensure_future(candidate_next, loop=loop))
                    added += 1
            #if not added:
            #    # should not happen
            #    raise ValueError("Internal Error")


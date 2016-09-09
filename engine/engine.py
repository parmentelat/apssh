#!/usr/bin/env python3

import asyncio

debug = False
#debug = True

class Engine:
    """
    An Engine instance works on a set of Action
    objects
    It will orchestrate them until they are all complete,
    starting with the ones that have no requirements, 
    and then starting the othe ones as their requirements are satisfied

    Running an Action means executing its corun() method, which must be a coroutine

    In of this rough/early implementation: 
    (*) the result of `corun` is not yet taken into account to implement some
        logic about how the overall job should behave

    (*) exceptions are probably not well handled so it's not clear what should happen
        if corun raises an exception
    
    """

    def __init__(self, *actions):
        self.actions = actions
        self.actions = list(set(self.actions))

    def add(self, actions):
        self.actions += actions
        self.actions = list(set(self.actions))

    def list(self):
        """
        print internal actions as sorted in self.actions
        mostly useful after .order()
        """
        for action in self.actions:
            print(action)
        
    def _reset_marks(self):
        """
        reset Action._mark on all actions/nodes
        """
        for action in self.actions:
            action._mark = None

    def _backlinks(self):
        """
        initialize Action._successors on all actions/nodes
        as the reverse of Action.required
        """
        for action in self.actions:
            action._successors = []
        for action in self.actions:
            for req in action.required:
                req._successors.append(action)

    def order(self):
        """
        re-order self.actions so that the free actions a.k.a. entry points
        i.e. actions with no requirements, show up first
        performs minimum sanity check -- raise ValueError if the topology cannot be handled
        """
        # clear marks
        self._reset_marks()
        # reset self.actions, but of course set aside
        save = self.actions
        self.actions = []
        # mainloop
        while True:
            # detect a fixed point 
            changed = False
            # loop on unfinished business
            for action in save:
                # if there's no requirement (first pass),
                # or later on if all requirements have already been marked,
                # then we can mark this one
                has_unmarked_requirements = False
                for req in action.required:
                    if req._mark is None:
                        has_unmarked_requirements = True
                if not has_unmarked_requirements:
                    if debug: print("order: marking {}".format(action.label))
                    action._mark = True
                    self.actions.append(action)
                    save.remove(action)
                    changed = True
            if not save:
                # we're done
                break
            if not changed:
                if debug: print("order: loop makes no progress - we have a problem")
                raise ValueError("only acyclic graphs are supported")
        # if we still have actions here it's not quite good either
        if save:
            print("order: we have {} actions still in the pool and can't reach them from free actions")
            raise ValueError("cyclic graph")

    @staticmethod
    def ensure_future(action, loop):
        """
        this is the hook that lets us make sure the created Task object have a 
        backlink pointer to its correponding action
        """
        task = asyncio.ensure_future(action.corun(), loop=loop)
        task._action = action
        action._task = task
        return task

    def orchestrate(self, loop):
        """
        main entry point, that's what Engine is all about
        """
        # initialize
        self._backlinks()
        # count how many actions have completed
        count_done = 0
        nb_actions = len(self.actions)

        # start with the free actions
        entry_actions = [ action for action in self.actions if not action.required ]

        if not entry_actions:
            raise ValueError("No entry points found - cannot orchestrate")
        
        pending = [ Engine.ensure_future(action, loop=loop)
                    for action in entry_actions ]
        
        while True:
            if debug: print("orchestrate: {} iteration {} / {}"
                            .format(10*'-', count_done,nb_actions))
            done, pending \
                = loop.run_until_complete(asyncio.wait(pending,
                                                       return_when = asyncio.FIRST_COMPLETED))
            # nominally we have exactly one item in done
            if not done or len(done) != 1:
                print("NOT GOOD - we're stalled ...")
                return False
            done_action = list(done)[0]._action

            count_done += 1
            if count_done == nb_actions:
                return True
            # only consider the ones that are right behind the action that just finished
            possible_next_actions = done_action._successors
            if debug:
                print("possible ->", len(possible_next_actions))
                for a in possible_next_actions:
                    print(a)
            # find out which ones really can be added
            added = 0
            for candidate_next in possible_next_actions:
                # do not add an action twice
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


####################
if __name__ == '__main__':

    from action import Action
    from testactions import SleepAction as SL

    def test_ko():
        """a simple loop"""
        actions = SL(1.1), SL(1.2), SL(1.3), SL(1.4), SL(1.5), SL(1.6), SL(1.7)
        a1, a2, a3, a4, a5, a6, a7 = actions
        a1.requires(a2)
        a2.requires(a3)
        a3.requires(a1)

        e = Engine(a1, a2, a3)
        e.order()
        e.list()

    try:
        test_ko()
    except Exception as e:
        print("failed", e)

    def test_ok():
        actions = SL(0.1), SL(0.2), SL(0.3), SL(0.4), SL(0.5), SL(0.6), SL(0.7)
        a1, a2, a3, a4, a5, a6, a7 = actions
        a4.requires(a1, a2, a3)
        a5.requires(a4)
        a6.requires(a4)
        a7.requires(a5)
        a7.requires(a6)
        
        e = Engine(*actions)
        e.order()
        e.list()
        print("orchestrate->", e.orchestrate(asyncio.get_event_loop()))
        e.list()
        

    test_ok()

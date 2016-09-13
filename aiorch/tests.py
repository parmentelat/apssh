"""
A simple tool to define ad-hoc 'jobs' 
"""

import time
import math
import asyncio

def ts():
    """ 
    a time stamp with millisecond 
    """
    # apparently this is not supported by strftime ?!?
    cl = time.time()
    ms = int(1000 * (cl-math.floor(cl)))
    return time.strftime("%M-%S-") + "{:03d}".format(ms)

##############################
async def _sl(n, middle, emergency):
    """
_sl(timeout, middle=False) returns a future that specifies an job like this:
* print incoming `->`
* wait for the time out
* print outgoing `<-` 
* return the timeout

_sl(timeout, middle=True) returns a future that specifies an job like this:
* print incoming `->`
* wait for half the time out
* print inside `==` - and optionnally raise an exception there if `emergency` is set
* wait for the second half of the time out
* print outgoing `<-` 
* return the timeout

"""
    print("{} -> sl({})".format(ts(), n))
    if middle:
        await asyncio.sleep(n/2)
        print("{} == sl({})".format(ts(), n))
        if emergency:
            raise Exception("emergency exit")
        await asyncio.sleep(n/2)
    else:
        await asyncio.sleep(n)
    print("{} <- sl({})".format(ts(), n))
    return n

def sl(n): return _sl(n, middle=False, emergency=False)
def slm(n): return _sl(n, middle=True, emergency=False)

##############################
from job import AbstractJob

class SleepJob(AbstractJob):
    def __init__(self, timeout, middle=False):
        AbstractJob.__init__(self, forever=False, label="sleep for {}s".format(timeout))
        self.timeout = timeout
        self.middle = middle

    async def co_run(self):
        result = await _sl(self.timeout, middle=self.middle, emergency=False)
        return result
        

class TickJob(AbstractJob):
    def __init__(self, cycle):
        AbstractJob.__init__(self, forever=True, label="Cyclic tick every {}s".format(cycle))
        self.cycle = cycle

    async def co_run(self):
        counter = 1
        while True:
            print("{} -- Tick {} from {}".format(ts(), counter, self.label))
            counter += 1
            await asyncio.sleep(self.cycle)


async def co_exception(n):
    await asyncio.sleep(n)
    raise ValueError(10**6*n)
    
####################            
from job import Job as J
from engine import Engine

# shortcuts
SLJ = SleepJob
TJ  = TickJob

import unittest

class Tests(unittest.TestCase):

    ####################
    def test_cycle(self):
        """a simple loop with 3 jobs - cannot handle that"""
        a1, a2, a3 = J(sl(1.1)), J(sl(1.2)), J(sl(1.3))
        a1.requires(a2)
        a2.requires(a3)
        a3.requires(a1)

        e = Engine(a1, a2, a3)
        # these lines seem to trigger a nasty message about a coro not being waited
        self.assertFalse(e.rain_check())

    ####################
    # Job(asyncio.sleep(0.4))
    # or
    # SleepJob(0.4)
    # are almost equivalent forms to do the same thing
    def test_simple(self):
        """a simple topology, that should work"""
        jobs = SLJ(0.1), SLJ(0.2), SLJ(0.3), SLJ(0.4), SLJ(0.5), J(sl(0.6)), J(sl(0.7))
        a1, a2, a3, a4, a5, a6, a7 = jobs
        a4.requires(a1, a2, a3)
        a5.requires(a4)
        a6.requires(a4)
        a7.requires(a5)
        a7.requires(a6)
        
        e = Engine(*jobs)
        self.assertTrue(e.orchestrate(loop=asyncio.get_event_loop()))
        e.list()
        
    ####################
    def test_forever(self):
        a1, a2, t1 = SLJ(1), SLJ(1.5), TJ(.6)
        a2.requires(a1)
        e = Engine(a1, a2, t1)
        e.list()
        self.assertTrue(e.orchestrate())
        e.list()

    ####################
    def test_timeout(self):
        a1, a2, a3 = [SLJ(x) for x in (0.5, 0.6, 0.7)]
        a2.requires(a1)
        a3.requires(a2)
        e = Engine(a1, a2, a3)
        # should timeout in the middle of stage 2
        self.assertFalse(e.orchestrate(timeout=1))
        e.list()

    ####################
    def test_exc_non_critical(self):

        a1, a2 = SLJ(1), J(co_exception(0.5), label='non critical boom')
        e = Engine(a1, a2)
        self.assertTrue(e.orchestrate())
        e.list()

    ####################
    def test_exc_critical(self):

        a1, a2 = SLJ(1), J(co_exception(0.5), label='critical boom', critical=True)
        e = Engine(a1, a2)
        self.assertFalse(e.orchestrate())
        e.list()

if __name__ == '__main__':
    import sys
    if '-v' in sys.argv:
        import engine
        engine.debug = True
        sys.argv.remove('-v')
    unittest.main()


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

    async def corun(self):
        result = await _sl(self.timeout, middle=self.middle, emergency=False)
        return result
        

class TickJob(AbstractJob):
    def __init__(self, cycle):
        AbstractJob.__init__(self, forever=True, label="Cyclic tick every {}s".format(cycle))
        self.cycle = cycle

    async def corun(self):
        counter = 1
        while True:
            print("{} -- Tick {} from {}".format(ts(), counter, self.label))
            counter += 1
            await asyncio.sleep(self.cycle)

from job import Job as A
import engine
from engine import Engine
engine.debug = True

####################
if __name__ == '__main__':

    ####################
    def test_cycle():
        """a simple loop with 3 jobs - cannot handle that"""
        print(20*'-', 'test_cycle')
        a1, a2, a3 = A(sl(1.1)), A(sl(1.2)), A(sl(1.3))
        a1.requires(a2)
        a2.requires(a3)
        a3.requires(a1)

        e = Engine(a1, a2, a3)
#        e.order()
#        e.list()

    try:
#        test_cycle()
        pass
    except Exception as e:
        print("failed", e)

    ####################
    from tests import SleepJob as SLA
    # Job(asyncio.sleep(0.4))
    # or
    # SleepJob(0.4)
    # are almost equivalent forms to do the same thing
    def test_simple():
        """a simple topology, that should work"""
        print(20*'-', 'test_simple')
        jobs = SLA(0.1), SLA(0.2), SLA(0.3), SLA(0.4), SLA(0.5), A(sl(0.6)), A(sl(0.7))
        a1, a2, a3, a4, a5, a6, a7 = jobs
        a4.requires(a1, a2, a3)
        a5.requires(a4)
        a6.requires(a4)
        a7.requires(a5)
        a7.requires(a6)
        
        e = Engine(*jobs)
        e.order()
        print("orchestrate->", e.orchestrate(asyncio.get_event_loop()))
        e.list()
        
#    test_simple()

    ####################
    from tests import TickJob as TA

    def test_forever():
        print(20*'-', 'test_forever')
        a1, a2, t1 = SLA(1), SLA(1.5), TA(.6)
        a2.requires(a1)
        e = Engine(a1, a2, t1)
        e.list()
        print("orchestrate->", e.orchestrate(asyncio.get_event_loop()))
        e.list()

#    test_forever()
        

    ####################
    def test_timeout():
        print(20*'-', 'test_timeout')
        a1, a2, a3 = [SLA(x) for x in (0.5, 0.6, 0.7)]
        a2.requires(a1)
        a3.requires(a2)
        e = Engine(a1, a2, a3)
        # should timeout in the middle of stage 2
        e.orchestrate(timeout=1)
        e.list()

    test_timeout()

    ####################
    async def coro_exc(n):
        await asyncio.sleep(n)
        raise ValueError(10**6*n)
    
    def test_exc():
        print(20*'-', 'test_exc')
        a1, a2 = SLA(1), A(coro_exc(0.5), label='boom')
        e = Engine(a1, a2)
        e.orchestrate()
        e.list()

    test_exc()

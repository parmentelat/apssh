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
        AbstractJob.__init__(self, "sleep for {}s".format(timeout))
        self.timeout = timeout
        self.middle = middle

    async def corun(self):
        result = await _sl(self.timeout, middle=self.middle, emergency=False)
        return result
        

class TickJob(AbstractJob):
    def __init__(self, cycle, *args, **kwds):
        AbstractJob.__init__(self, "Cyclic tick every {}s".format(cycle), *args, **kwds)
        self.cycle = cycle

    def corun(self):
        counter = 1
        while True:
            print("{} -- Tick {} from {}".format(ts(), counter, self.label))
            counter += 1
            asyncio.sleep(self.cycle)

####################
if __name__ == '__main__':

    from job import Job as A
    from engine import Engine

    ####################
    def test_ko():
        """a simple loop with 3 jobs - cannot handle that"""
        print(20*'-', 'test_ko')
        a1, a2, a3 = A(sl(1.1)), A(sl(1.2)), A(sl(1.3))
        a1.requires(a2)
        a2.requires(a3)
        a3.requires(a1)

        e = Engine(a1, a2, a3)
        e.order()
#        e.list()

    try:
        test_ko()
    except Exception as e:
        print("failed", e)

    ####################
    from tests import SleepJob as SLA
    # Job(asyncio.sleep(0.4))
    # or
    # SleepJob(0.4)
    # are almost equivalent forms to do the same thing
    def test_ok():
        """a simple topology, that should work"""
        print(20*'-', 'test_ok')
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
        
    test_ok()

    ####################
    from tests import TickJob as TA

    def test_infinite():
        print(20*'-', 'test_infinite')
        a1, a2, t1 = SLA(1), SLA(1.5), TA(0.4)
        a2.requires(a1)
        e = Engine(a1, a2, t1)
        print("orchestrate->", e.orchestrate(asyncio.get_event_loop()))
        e.list()

    #test_infinite()
        
    

"""
A simple tool to define ad-hoc 'actions' 
"""

import time
import math
import asyncio

def ts():
    """ 
    a time stamp with millisecond 
    """
    # apparently this is not supported by strftime ?!?
    cl = time.clock()
    ms = int(1000 * (cl-math.floor(cl)))
    return time.strftime("%M-%S-") + "{}".format(ms)

##############################
async def _sl(n, middle, emergency):
    """
_sl(timeout, middle=False) returns a future that specifies an action like this:
* print incoming `->`
* wait for the time out
* print outgoing `<-` 
* return the timeout

_sl(timeout, middle=True) returns a future that specifies an action like this:
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
from action import AbstractAction

class SleepAction(AbstractAction):
    def __init__(self, timeout, middle=False):
        AbstractAction.__init__(self, "sleep for {}s".format(timeout))
        self.timeout = timeout
        self.middle = middle

    async def corun(self):
        result = await _sl(self.timeout, middle=self.middle, emergency=False)
        return result
        

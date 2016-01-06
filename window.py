import asyncio

# xxx todo : connect this debug flag to -D as passed to main
debug = False
#debug = True

async def gather_window(*futures, window=1, loop=None, **kwds):
    """
    Performs like asyncio.gather but with a maximum of 
    <window> tasks active at any given time
    
    Ideally the default for window would be None and the whole thing
    could go in asyncio.gather; IOW, there is no need for a separate name
    """

    loop = loop if loop is not None else asyncio.get_event_loop()

    # create the queue that will throttle execution to <window> tasks
    queue = asyncio.Queue(maxsize=window, loop=loop)

    async def monitor_queue():
        await asyncio.sleep(3)
        while not queue.empty():
            print("queue has {}/{} elements busy"
                  .format(queue.qsize(), window))
            await asyncio.sleep(3.)

    # a decorator-like approach for this aspect
    def wrap(future):
        async def wrapped():
            # take a slot in the queue
            # what we actually put in the queue does not matter
            await queue.put(1)
            value = await future
            # release slot in the queue
            await queue.get()
            # return the right thing
            return value
        # return the coroutine itself
        # it will need to be called though
        return wrapped

    # here we do the call           vv     on the wrapped coroutine
    wrapped_futures = [ wrap(future)() for future in futures ]
    if debug:
        wrapped_futures.append(monitor_queue())
    overall = await asyncio.gather(*wrapped_futures, loop=loop, **kwds)
    return overall

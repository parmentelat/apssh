import asyncio

async def gather_window(*futures, window=1, loop=None, debug=False, **kwds):
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

############################## a basic test for gather_window
def test_gather_window():
    """
    a simple tool for testing gather_window
    """

    async def tick(id, n):
        for i in range(n):
            print("id={} - tick {}".format(id, i))
            await asyncio.sleep(0.5)
        return id

    parser = ArgumentParser()
    parser.add_argument("-w", "--window", default=None, type=int,
                        help="default is to use regular asyncio.gather")
    parser.add_argument("-f", "--from", dest='from_arg', default=1, type=int)
    parser.add_argument("-t", "--to", default=3, type=int)
    args = parser.parse_args()

    assert args.from_arg < args.to, "need to define from < to"

    r = range(args.from_arg, args.to) 
    issued = [ print("Creating tick({})".format(x)) for x in r ]

    ticks = [ tick(i, i) for i in r ]

    if args.window:
        print("Using window={}".format(args.window))
        results = asyncio.get_event_loop().run_until_complete(
            gather_window(*ticks, window=args.window))
    else:
        print("Using regular gather")
        results = asyncio.get_event_loop().run_until_complete(
            asyncio.gather(*ticks))

        print(results)

if __name__ == '__main__':
    test_gather_window()

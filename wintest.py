#!/usr/bin/env python3

"""
a simple tool for testing gather_window
"""

import asyncio
from argparse import ArgumentParser

from window import gather_window

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
    results = asyncio.get_event_loop().run_until_complete(gather_window(*ticks, window=args.window))
else:
    print("Using regular gather")
    results = asyncio.get_event_loop().run_until_complete(asyncio.gather(*ticks))

print(results)

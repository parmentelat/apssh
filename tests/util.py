# pylint: disable=c0111

import asyncio

from pathlib import Path

from asynciojobs import Watch, Job, Scheduler


async def co_print_sleep(watch, duration, message):
    # if start_watch was not called, show time with milliseconds
    if watch is None:
        Watch.print_wall_clock()
    else:
        watch.print_elapsed()
    print(message)
    await asyncio.sleep(duration)
    return f"duration={duration}"


def produce_png(scheduler, name):
    dot = scheduler.graph()
    dot.format = 'png'

    tests_dir = Path('tests')
    if tests_dir.exists():
        actual_name = str(tests_dir / name)
    else:
        actual_name = name
    dot.render(actual_name)
    print(f"png file produced in {actual_name}{{,.png}}")


def diamond_scheduler(watch, duration, msg, scheduler_class=Scheduler):
    """
    create a small diamond scheduler
    total duration = duration
    """
    diamond = scheduler_class(watch=watch)
    top = Job(co_print_sleep(watch, duration/4, f"top {msg}"),
              label=f"top {msg}1",
              scheduler=diamond)
    left = Job(co_print_sleep(watch, duration/2, f"left {msg}"),
               label=f"left {msg}",
               required=top, scheduler=diamond)
    right = Job(co_print_sleep(watch, duration/2, f"right {msg}", ),
                label=f"right {msg}",
                required=top, scheduler=diamond)
    Job(co_print_sleep(watch, duration / 4, f"bottom {msg}"),
        label=f"bottom {msg}",
        required=(left, right), scheduler=diamond)
    return diamond


def pipes(watch, duration, msg, *,
          nb_pipes=2, scheduler_class=Scheduler):
    """
    2 pipes of 2 jobs each
    total duration = duration
    """
    sched = scheduler_class(watch=watch)
    for i in range(1, nb_pipes+1):
        top = Job(co_print_sleep(watch, duration/2, f"top{i} {msg}"),
                  label=f"top{i} {msg}")
        bottom = Job(co_print_sleep(watch, duration/2, f"bot{i} {msg}"),
                     label=f"bot{i} {msg}",
                     required=top)
        sched.add(top).add(bottom)
    return sched

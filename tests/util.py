# pylint: disable=c0111

import asyncio

from pathlib import Path

from asynciojobs import Watch, Job, Scheduler

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

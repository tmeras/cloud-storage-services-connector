import contextlib
import logging
import time
from enum import Enum

from termcolor import colored


class PrintStyle(Enum):
    INFO = 1
    WARNING = 2
    ERROR = 3
    SUCCESS = 4


def print_string(s, style=PrintStyle.INFO):
    match style:
        case PrintStyle.INFO:
            print(s)
        case PrintStyle.WARNING:
            print(colored(s, "yellow"))
        case PrintStyle.ERROR:
            print(colored(s, "red"))
        case PrintStyle.SUCCESS:
            print(colored(s, "green", attrs=["bold"]))


@contextlib.contextmanager
def stopwatch(message):
    """
    Context manager to print how long a block of code took.
    """
    t0 = time.time()
    try:
        yield
    finally:
        t1 = time.time()
        logging.info('Total elapsed time for %s: %.3f seconds' % (message, t1 - t0))

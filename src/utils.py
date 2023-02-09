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


def yesno(message, default):
    """
    Handy helper function to ask a yes/no question.
    Special answers:
    - q or quit exits the program
    - p or pdb invokes the debugger
    """
    if default:
        message += '? [Y/n] '
    else:
        message += '? [N/y] '
    while True:
        answer = input(message).strip().lower()
        if not answer:
            return default
        if answer in ('y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        if answer in ('q', 'quit'):
            print('Exit')
            raise SystemExit(0)
        if answer in ('p', 'pdb'):
            import pdb
            pdb.set_trace()
        print_string('Please answer YES or NO',PrintStyle.WARNING)


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

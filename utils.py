from datetime import datetime
from sys import exc_info
from traceback import format_exc, format_list, extract_stack

"""

Meower Utils Module
This module provides logging, error traceback, and other miscellaneous utilities.

This file should never rely on other Meower modules to prevent circular imports.
"""

def full_stack():
    """
    Print out the full traceback.
    """

    exc = exc_info()[0]
    if exc is not None:
        f = exc_info()[-1].tb_frame.f_back
        stack = extract_stack(f)
    else:
        stack = extract_stack()[:-1]
    trc = 'Traceback (most recent call last):\n'
    stackstr = trc + ''.join(format_list(stack))
    if exc is not None:
        stackstr += '  ' + format_exc().lstrip(trc)
    return stackstr


def log(event: str):
    """
    Print out a log with the current date & time to the Python console.
    """

    timestamp = datetime.now().strftime("%m/%d/%Y %H:%M.%S")

    print("{0}: {1}".format(timestamp, event))

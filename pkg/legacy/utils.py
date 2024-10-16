from datetime import datetime
import sys
import traceback

"""

Meower Utils Module
This module provides logging, error traceback, and other miscellaneous utilities.

This file should never rely on other Meower modules to prevent circular imports.
"""

def full_stack():
    """
    Print out the full traceback.
    """

    exc = sys.exc_info()[0]
    if exc is not None:
        f = sys.exc_info()[-1].tb_frame.f_back
        stack = traceback.extract_stack(f)
    else:
        stack = traceback.extract_stack()[:-1]
    trc = 'Traceback (most recent call last):\n'
    stackstr = trc + ''.join(traceback.format_list(stack))
    if exc is not None:
        stackstr += '  ' + traceback.format_exc().lstrip(trc)
    return stackstr

def log(event: str):
    """
    Print out a log with the current date & time to the Python console.
    """

    print("{0}: {1}".format(datetime.now().strftime("%m/%d/%Y %H:%M.%S"), event))

from typing import Literal
from datetime import datetime
import time
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

def timestamp(ttype: Literal[1, 2, 3, 4, 5]):
    """
    Get a timestamp in various flavours.

    | ttype | description |
    |-|-|
    | 1 | full/extended |
    | 2 | %H%M%S |
    | 3 | %d%m%Y%H%M%S |
    | 4 | %m/%d/%Y %H:%M.%S |
    | 5 | %d%m%Y |
    """ 

    today = datetime.now()
    if ttype == 1:
        return {
            "mo": (datetime.now()).strftime("%m"),
            "d": (datetime.now()).strftime("%d"),
            "y": (datetime.now()).strftime("%Y"),
            "h": (datetime.now()).strftime("%H"),
            "mi": (datetime.now()).strftime("%M"),
            "s": (datetime.now()).strftime("%S"),
            "e": (int(time.time()))
        }
    elif ttype == 2:
        return str(today.strftime("%H%M%S"))
    elif ttype == 3:
        return str(today.strftime("%d%m%Y%H%M%S"))
    elif ttype == 4:
        return today.strftime("%m/%d/%Y %H:%M.%S")
    elif ttype == 5:    
        return today.strftime("%d%m%Y")
    
def log(event: str):
    """
    Print out a log with the current date & time to the Python console.
    """

    print("{0}: {1}".format(timestamp(4), event))

from __main__ import meower
from datetime import datetime
import time
import secrets

def log(msg, prefix=None):
    timestamp = timestamp(4)
    if prefix is None:
        print("{0}: {1}".format(timestamp, msg))
    else:
        print("[{0}] {1}: {2}".format(prefix, timestamp, msg))

def timestamp(ttype, epoch=int(time.time())):
    today = datetime.fromtimestamp(epoch)
    if ttype == 1:
        return dict({
            "mo": str(datetime.now().strftime("%m")),
            "d": str(datetime.now().strftime("%d")),
            "y": str(datetime.now().strftime("%Y")),
            "h": str(datetime.now().strftime("%H")),
            "mi": str(datetime.now().strftime("%M")),
            "s": str(datetime.now().strftime("%S")),
            "e": int(time.time())
        })
    elif ttype == 2:
        return str(today.strftime("%H%M%S"))
    elif ttype == 3:
        return str(today.strftime("%d%m%Y%H%M%S"))
    elif ttype == 4:
        return str(today.strftime("%m/%d/%Y %H:%M.%S"))
    elif ttype == 5:    
        return str(today.strftime("%d%m%Y"))

def generate_token(length=64):
    return "{0}.{1}".format(str(secrets.token_urlsafe(length)), float(time.time()))
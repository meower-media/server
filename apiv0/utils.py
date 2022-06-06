from __main__ import meower
from datetime import datetime
import time
import string
import secrets

# Create permitted lists of characters for posts
permitted_chars_post = []
permitted_chars_post.extend(string.ascii_letters)
permitted_chars_post.extend(string.digits)
permitted_chars_post.extend(string.punctuation)
permitted_chars_post.append(" ")

# Create permitted lists of characters for usernames
permitted_chars_username = permitted_chars_post.copy()
for item in [
    '"',
    "'",
    "*",
    ";"
]:
    permitted_chars_username.remove(item)

def log(msg, prefix=None):
    if prefix is None:
        print("{0}: {1}".format(timestamp(4), msg))
    else:
        print("[{0}] {1}: {2}".format(prefix, timestamp(4), msg))

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

def check_for_bad_chars_username(message):
    for char in message:
        if not char in permitted_chars_username:
            return True
    return False

def check_for_bad_chars_post(message):
    for char in message:
        if not char in permitted_chars_post:
            return True
    return False
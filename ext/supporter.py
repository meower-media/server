from datetime import datetime
from better_profanity import profanity
import time
import traceback
import sys
import string
from uuid import uuid4

"""

Meower Supporter Module

This module provides logging, error traceback, and other miscellaneous supportive functionality.
This keeps the main.py clean and more understandable.

"""

class Supporter:
    def __init__(self, meower):
        self.meower = meower

        self.repair_mode = True
        self.is_deprecated = True
        self.profanity = profanity
        self.profanity.load_censor_words()
        self.ratelimits = {}
        
        # Create permitted lists of characters for posts
        self.permitted_chars_post = []
        self.permitted_chars_post.extend(string.ascii_letters)
        self.permitted_chars_post.extend(string.digits)
        self.permitted_chars_post.extend(string.punctuation)
        self.permitted_chars_post.append(" ")

        # Create permitted lists of characters for usernames
        self.permitted_chars_username = self.permitted_chars_post.copy()
        for item in [
            '"',
            "'",
            "*",
            ";"
        ]:
            self.permitted_chars_username.remove(item)
        
        self.log("Supporter initialized!")
    
    def full_stack(self):
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
    
    def log(self, msg, prefix=None):
        timestamp = self.timestamp(4)
        if prefix is None:
            print("{0}: {1}".format(timestamp, msg))
        else:
            print("[{0}] {1}: {2}".format(prefix, timestamp, msg))
    
    def timestamp(self, ttype, epoch=int(time.time())):
        today = datetime.fromtimestamp(epoch)
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
        elif ttype == 6:
            return int(time.time())
        elif ttype == 7:
            return float(time.time())
    
    def ratelimit(self, username):
        # Rate limiter
        self.ratelimits[str(username)] = time.time()+1
    
    def filter(self, message):
        # Word censor
        if self.profanity != None:
            message = self.profanity.censor(message)
        else:
            self.log("Failed loading profanity filter : Using default filter as fallback")
            profanity.load_censor_words()
            message = profanity.censor(message)
        return message
    
    def checkForBadCharsUsername(self, value):
        # Check for profanity in username, will return '*' if there's profanity which will be blocked as an illegal character
        value = self.filter(value)

        badchars = False
        for char in value:
            if not char in self.permitted_chars_username:
                badchars = True
                break
        return badchars
        
    def checkForBadCharsPost(self, value):
        badchars = False
        for char in value:
            if not char in self.permitted_chars_post:
                badchars = True
                break
        return badchars
    
    def checkForMalformedEmail(self, value):
        tmp = value.split("@")
        if len(tmp) == 2:
            if len(tmp[0]) >= 1:
                return False
            else:
                return True
        else:
            return True
    
    def check_for_spam(self, username):
        if str(username) in self.ratelimits:
            return ((self.ratelimits[str(username)]) > self.timestamp(7))
        else:
            return False
        
    def uuid(self):
        return str(uuid4())
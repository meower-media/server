from datetime import datetime
from better_profanity import profanity
import time
import traceback
import sys
import string
import json

"""

Meower Supporter Module

This module provides logging, error traceback, and other miscellaneous supportive functionality.
This keeps the main.py clean and more understandable.

"""

class Supporter:
    def __init__(self, cl=None, packet_callback=None):
        self.cl = cl
        self.profanity = profanity
        self.packet_handler = packet_callback
        self.listener_detected = False
        self.listener_id = None
        
        if not self.cl == None:
            # Add custom status codes to CloudLink
            self.cl.codes["KeyNotFound"] = "I:010 | Key Not Found"
            self.cl.codes["PasswordInvalid"] = "I:011 | Invalid Password"
            self.cl.codes["GettingReady"] = "I:012 | Getting ready"
            self.cl.codes["ObsoleteClient"] = "I:013 | Client is out-of-date or unsupported"
            self.cl.codes["Pong"] = "I:014 | Pong"
            self.cl.codes["IDExists"] = "I:015 | Account exists"
            self.cl.codes["2FAOnly"] = "I:016 | 2FA Required"
            self.cl.codes["MissingPermissions"] = "I:017 | Missing permissions"
            self.cl.codes["Banned"] = "E:018 | Account Banned"
            self.cl.codes["IllegalChars"] = "E:019 | Illegal characters detected"
            self.cl.codes["Kicked"] = "E:020 | Kicked"
            self.cl.codes["ChatExists"] = "E:021 | Chat exists"
            self.cl.codes["ChatNotFound"] = "E:022 | Chat not found"
        
        # Create permitted lists of characters
        self.permitted_chars_username = []
        self.permitted_chars_post = []
        for char in string.ascii_letters:
            self.permitted_chars_username.append(char)
            self.permitted_chars_post.append(char)
        for char in string.digits:
            self.permitted_chars_username.append(char)
            self.permitted_chars_post.append(char)
        for char in string.punctuation:
            self.permitted_chars_post.append(char)
        self.permitted_chars_post.append(" ")
        
        # Create chats
        self.chats = {}
        
        """
        
        Example reference for chats (excluding livechat, as that chat is purely stateless)
        
        self.chats = {
            "(Chat unique ID)": {
                "nickname": "foobarchat",
                "owner": "MikeDEV",
                "userlist": [
                    "MikeDEV"
                ]
            }
        }
        """
        
        # Peak number of users logger
        self.peak_users_logger = {
            "count": 0,
            "timestamp": {
                "mo": 0,
                "d": 0,
                "y": 0,
                "h": 0,
                "mi": 0,
                "s": 0
            }
        }
        
        if not self.cl == None:
            # Specify server callbacks
            self.cl.callback("on_packet", self.on_packet)
            self.cl.callback("on_close", self.on_close)
            self.cl.callback("on_connect", self.on_connect)
        
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
    
    def log(self, event):
        print("{0}: {1}".format(self.timestamp(4), event))
    
    def sendPacket(self, payload, listener_detected=False, listener_id=None):
        if not self.cl == None:
            if listener_detected:
                if "id" in payload:
                    payload["listener"] = listener_id
                self.cl.sendPacket(payload)
            else:
                self.cl.sendPacket(payload)
    
    def get_client_statedata(self, client): # "steals" information from the CloudLink module to get better client data
        if not self.cl == None:
            if type(client) == str:
                client = self.cl._get_obj_of_username(client)
            if not client == None:
                if client['id'] in self.cl.statedata["ulist"]["objs"]:
                    tmp = self.cl.statedata["ulist"]["objs"][client['id']]
                    return tmp
                else:
                    return None
    
    def modify_client_statedata(self, client, key, newvalue): # WARN: Use with caution: DO NOT DELETE UNNECESSARY KEYS!
        if not self.cl == None:
            if type(client) == str:
                client = self.cl._get_obj_of_username(client)
            if not client == None:
                if client['id'] in self.cl.statedata["ulist"]["objs"]:
                    try:
                        self.cl.statedata["ulist"]["objs"][client['id']][key] = newvalue
                        return True
                    except:
                        self.log("{0}".format(self.full_stack()))
                        return False
                else:
                    return False
    
    def delete_client_statedata(self, client, key): # WARN: Use with caution: DO NOT DELETE UNNECESSARY KEYS!
        if not self.cl == None:
            if type(client) == str:
                client = self.cl._get_obj_of_username(client)
            if not client == None:
                if client['id'] in self.cl.statedata["ulist"]["objs"]:
                    if key in self.cl.statedata["ulist"]["objs"][client['id']]:
                        try:
                            del self.cl.statedata["ulist"]["objs"][client['id']][key]
                            return True
                        except:
                            self.log("{0}".format(self.full_stack()))
                            return False
                else:
                    return False
    
    def log_peak_users(self):
        if not self.cl == None:
            current_users = len(self.cl.getUsernames())
            if current_users > self.peak_users_logger["count"]:
                today = datetime.now()
                self.peak_users_logger = {
                    "count": current_users,
                    "timestamp": {
                        "mo": (datetime.now()).strftime("%m"),
                        "d": (datetime.now()).strftime("%d"),
                        "y": (datetime.now()).strftime("%Y"),
                        "h": (datetime.now()).strftime("%H"),
                        "mi": (datetime.now()).strftime("%M"),
                        "s": (datetime.now()).strftime("%S")
                    }
                }
                self.log("New peak in # of concurrent users: {0}".format(current_users))
                #self.create_system_message("Yay! New peak in # of concurrent users: {0}".format(current_users))
                payload = {
                    "mode": "peak",
                    "payload": self.peak_users_logger
                }
                self.sendPacket({"cmd": "direct", "val": payload})
    
    def on_close(self, client):
        if not self.cl == None:
            if type(client) == dict:
                self.log("{0} Disconnected.".format(client["id"]))
            elif type(client) == str:
                self.log("{0} Logged out.".format(self.cl._get_username_of_obj(client)))
            self.log_peak_users()
    
    def on_connect(self, client):
        if not self.cl == None:
            self.log("{0} Connected.".format(client["id"]))
            self.modify_client_statedata(client, "authtype", "")
            self.modify_client_statedata(client, "authed", False)
            
            # Rate limiter
            self.modify_client_statedata(client, "last_packet", 0)
    
    def on_packet(self, message):
        if not self.cl == None:
            # CL Turbo Support
            self.listener_detected = ("listener" in message)
            self.listener_id = None
            
            if self.listener_detected:
                self.listener_id = message["listener"]
            
            # Read packet contents
            id = message["id"]
            val = message["val"]
            clienttype = None
            client = message["id"]
            if type(message["id"]) == dict:
                ip = self.cl.getIPofObject(client)
                clienttype = 0
            elif type(message["id"]) == str:
                ip = self.cl.getIPofUsername(client)
                clienttype = 1
            
            # Handle packet
            cmd = None
            if "cmd" in message:    
                cmd = message["cmd"]
            
            if not self.packet_handler == None:
                self.packet_handler(cmd, ip, val, self.listener_detected, self.listener_id, client, clienttype)
    
    def timestamp(self, ttype):
        today = datetime.now()
        if ttype == 1:
            return {
                "t": {
                        "mo": (datetime.now()).strftime("%m"),
                        "d": (datetime.now()).strftime("%d"),
                        "y": (datetime.now()).strftime("%Y"),
                        "h": (datetime.now()).strftime("%H"),
                        "mi": (datetime.now()).strftime("%M"),
                        "s": (datetime.now()).strftime("%S")
                    }
                }
        elif ttype == 2:
            return str(today.strftime("%H%M%S"))
        elif ttype == 3:
            return str(today.strftime("%d%m%Y%H%M%S"))
        elif ttype == 4:
            return today.strftime("%m/%d/%Y %H:%M.%S")
        elif ttype == 5:    
            return today.strftime("%d%m%Y")
    
    def ratelimit(self, client):
        # Rate limiter
        self.modify_client_statedata(client, "last_packet", int(time.time()))
    
    def wordfilter(self, message):
        return self.profanity.censor(message)
    
    def isAuthenticated(self, client):
        if not self.cl == None:
            return self.get_client_statedata(client)["authed"]
    
    def setAuthenticatedState(self, client, value):
        if not self.cl == None:
            self.modify_client_statedata(client, "authed", value)
    
    def checkForBadCharsUsername(self, value):
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
    
    def autoID(self, client, username):
        if not self.cl == None:
            # really janky code that automatically sets user ID
            if self.get_client_statedata(client)["type"] != "scratch": # Prevent this from breaking compatibility with scratch clients
                self.modify_client_statedata(client, "username", username)
                self.cl.statedata["ulist"]["usernames"][username] = client["id"]
                self.sendPacket({"cmd": "ulist", "val": self.cl._get_ulist()})
                self.log("{0} autoID given".format(username))
    
    def kickBadUsers(self, username):
        if not self.cl == None:
            # Check for clients that are trying to steal the ID and kick em' / Disconnect other sessions
            if username in self.cl.getUsernames():
                self.log("Detected someone trying to use the username {0} wrongly".format(username))
                self.cl.kickClient(username)
    
    def check_for_spam(self, client):
        if not self.cl == None:
            return ((self.get_client_statedata(client)["last_packet"]) < (int(time.time())))

from threading import Thread
from uuid import uuid4
import json
import time
import secrets

class Socket:
    def __init__(self, meower, client):
        self.meower = meower
        self.client = client

        self.client.id = self.meower.sock_next_id
        self.meower.sock_next_id += 1
        self.client.login_code = None
        self.client.user = None
        self.statuscodes = {
            "OK": "I:100 | OK",
            "Syntax": "E:101 | Syntax",
            "Datatype": "E:102 | Datatype",
            "TooLarge": "E:103 | Packet too large",
            "Internal": "E:104 | Internal",
            "InvalidToken": "E:106 | Invalid token",
            "Refused": "E:107 | Refused",
            "IDNotFound": "E:108 | ID not found",
            "RateLimit": "E:109 | Too many requests"
        }

        while True:
            msg = self.client.receive(1024)
            Thread(target=self.handle_msg, args=(msg,)).start()
    
    def handle_msg(self, msg):
        try:
            msg = json.loads(msg)
        except:
            return self.send_status("Datatype")
        
        if not (("cmd" in msg) and ("val" in msg)):
            return self.send_status("Syntax")

        self.meower.log("Handling '{0}' from: {1}".format(msg["cmd"], self.client.id))

        cmd = msg["cmd"]
        val = msg["val"]
        if "listener" in msg:
            listener = msg["listener"]
        else:
            listener = None
        
        try:
            {
                "ping": self.ping,
                "gen_code": self.gen_code,
                "auth": self.auth,
                "get_profile": self.get_profile,
                "change_status": self.change_status
            }[cmd](val, listener=listener)
        except:
            return self.send_status("Internal", listener=listener)

    def send_status(self, status, listener=None):
        if listener is None:
            return self.client.send(json.dumps({"cmd": "statuscode", "val": self.statuscodes[status]}))
        else:
            return self.client.send(json.dumps({"cmd": "statuscode", "val": self.statuscodes[status], "listener": listener}))

    def ping(self, val, listener=None):
        return self.send_status("OK", listener=listener)

    def gen_code(self, val, listener=None):
        self.client.login_code = str(secrets.SystemRandom().randint(111111, 9999999))
        self.meower.sock_login_codes[self.client.login_code] = self
        self.client.send(json.dumps({"cmd": "gen_code", "val": self.client.login_code}))
        return self.send_status("OK", listener=listener)

    def auth(self, val, listener=None):
        if type(val) is not str:
            return self.send_status("Datatype", listener=listener)
        elif len(val) > 64:
            return self.send_status("TooLarge", listener=listener)
        
        session_data = self.meower.db["sessions"].find_one({"access_token": val, "access_expiry": {"$gt": int(time.time())}})
        if session_data is None:
            return self.send_status("InvalidToken", listener=listener)
        else:
            userdata = self.meower.db["usersv0"].find_one({"_id": session_data["user"]})
            self.client.user = session_data["user"]
            if not self.client.user in self.meower.sock_clients:
                self.meower.sock_clients[self.client.user] = []
            self.meower.sock_clients[self.client.user].append(self)
            self.meower.log("WebSocket client {0} with user {1} authenticated".format(self.client.id, self.client.user))
            self.client.send(json.dumps({"cmd": "auth", "val": {"user": self.client.user, "username": userdata["username"], "session": session_data["_id"]}}))
            return self.send_status("OK", listener=listener)

    def get_profile(self, val, listener=None):
        if type(val) is not str:
            return self.send_status("Datatype", listener=listener)
        elif len(val) > 20:
            return self.send_status("TooLarge", listener=listener)
        
        if val == "me":
            userdata = self.meower.db["usersv0"].find_one({"_id": self.client.user})
        else:
            userdata = self.meower.db["usersv0"].find_one({"lower_username": val.lower()})
        
        if userdata is None:
            return self.send_status("IDNotFound", listener=listener)
        else:
            if userdata["_id"] != self.client.user:
                del userdata["config"]
                del userdata["ratelimits"]
            else:
                userdata["config/mfa"] = (userdata["security"]["mfa_secret"] != None)
            del userdata["security"]
            userdata["profile"]["status"] = self.meower.user_status(userdata["_id"])

            self.client.send(json.dumps({"cmd": "get_profile", "val": userdata}))
            return self.send_status("OK", listener=listener)
    
    def change_status(self, val, listener=None):
        if type(val) is not int:
            return self.send_status("Datatype", listener=listener)
        elif not (val in [0, 1, 2, 3]):
            return self.send_status("Refused", listener=listener)
        self.meower.db["usersv0"].update_one({"_id": self.client.user}, {"$set": {"profile.status": val, "profile.last_seen": int(time.time())}})
        self.meower.log("User {0} changed status to {1}".format(self.client.user, val))
        return self.send_status("OK", listener=listener)
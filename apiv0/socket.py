from threading import Thread
from uuid import uuid4
import json

class Socket:
    def __init__(self, meower, client):
        self.meower = meower
        self.client = client

        self.client.id = str(uuid4())
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
            return self.send_status("Datatype", listener=listener)
        
        if not (("cmd" in msg) and ("val" in msg)):
            return self.send_status("Syntax", listener=listener)

        self.meower.log("Handling '{0}' from: {1}".format(msg["cmd"], self.client.id))

        cmd = msg["cmd"]
        val = msg["val"]
        if "listener" in msg:
            listener = msg["listener"]
        else:
            listener = None
        
        try:
            {
                "ping": self.ping
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
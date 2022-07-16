from flask import request
from threading import Thread
import json
from uuid import uuid4

class SocketClient:
    def __init__(self, meower, client):
        self.meower = meower
        self.client = client

        self.client.id = str(uuid4())
        self.client.session = None
        self.client.current_listener = None

        self.send("motd", "Meower Social Media Platform WebSocket Server")
        self.send("vers", "0.0.1")
        self.send("id", self.client.id)

        self.meower.log("{0} connected to WebSocket".format(self.client.id))
        Thread(target=self.handle_msg).start()
        while self.client.connected:
            pass
        if self.client.session is not None:
            self.meower.sock_clients[self.client.session.user].remove(self)
            if len(self.meower.sock_clients[self.client.session.user]) == 0:
                del self.meower.sock_clients[self.client.session.user]
        self.meower.log("{0} disconnected from WebSocket".format(self.client.id))

    def handle_msg(self):
        while True:
            msg = self.client.receive()
            try:
                msg = json.loads(msg)
            except:
                return self.send_status("Datatype")
            
            if not (("cmd" in msg) and ("val" in msg)):
                return self.send_status("Syntax")

            self.meower.log("Handling '{0}' from WebSocket client: {1}".format(msg["cmd"], self.client.id))

            cmd = msg["cmd"]
            val = msg["val"]
            if ("listener" in msg) and (len(msg["listener"]) < 100):
                self.client.current_listener = msg["listener"]
            else:
                self.client.current_listener = None
            
            try:
                {
                    "ping": self.ping,
                    "auth": self.auth
                }[cmd](val)
            except:
                self.send_status("Internal")
            self.client.current_listener = None

    def send(self, cmd, val):
        if self.client.current_listener is None:
            self.client.send(json.dumps({"cmd": cmd, "val": val}))
        else:
            self.client.send(json.dumps({"cmd": cmd, "val": val, "listener": self.client.current_listener}))

    def send_status(self, status):
        if self.client.current_listener is None:
            self.client.send(json.dumps({"cmd": "statuscode", "val": self.meower.sock_statuses[status]}))
        else:
            self.client.send(json.dumps({"cmd": "statuscode", "val": self.meower.sock_statuses[status], "listener": self.client.current_listener}))

    def ping(self, val):
        return self.send_status("OK")

    def auth(self, val):
        if self.client.session is not None:
            return self.send_status("OK")
        elif type(val) is not str:
            return self.send_status("Datatype")
        elif len(val) > 136:
            return self.send_status("TooLarge")

        val = val.replace("Bearer ", "").strip()
        
        session = self.meower.Session(self.meower, val)
        if session.authed and ("meower:websocket:connect" in session.scopes):
            self.client.session = session

            if session.user not in self.meower.sock_clients:
                self.meower.sock_clients[session.user] = []
            self.meower.sock_clients[session.user].append(self)

            # Return session data
            return self.send("auth", {"_id": self.client.session._id, "user": self.client.session.user, "scopes": self.client.session.scopes})
        else:
            return self.send_status("InvalidToken")
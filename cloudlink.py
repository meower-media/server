import websockets
import asyncio
import json
import time
import os
from typing import Optional, Iterable, TypedDict, Any
from urllib.parse import urlparse, parse_qs

import security
from utils import full_stack
from database import db

class CloudlinkPacket(TypedDict):
    cmd: str
    val: any
    listener: Optional[str]

class CloudlinkServer:
    def __init__(self):
        self.real_ip_header = os.getenv("REAL_IP_HEADER")
        self.statuscodes: dict[str, str] = {
            "OK": "I:100 | OK",
            "Syntax": "E:101 | Syntax",
            "Datatype": "E:102 | Datatype",
            "InternalServerError": "E:104 | Internal",
            "TAEnabled": "I:112 | Trusted Access enabled",
            "Invalid": "E:118 | Invalid command",
            "PasswordInvalid": "I:011 | Invalid Password",
            "Banned": "E:018 | Account Banned",
        }
        self.clients: set[CloudlinkClient] = set()
        self.usernames: dict[str, list[CloudlinkClient]] = {}  # {"username": [cl_client1, cl_client2, ...]}
    
    def get_ulist(self):
        ulist = ";".join(self.usernames.keys())
        if ulist:
            ulist += ";"
        return ulist

    async def client_handler(self, websocket: websockets.WebSocketServerProtocol):
        # Create CloudlinkClient
        cl_client = CloudlinkClient(self, websocket)

        # Add to websockets and clients sets
        self.clients.add(cl_client)

        # Send ulist
        cl_client.send("ulist", self.get_ulist())

        # Send Trusted Access statuscode
        if cl_client.proto_version == 0:
            cl_client.send_statuscode("TAEnabled")
            cl_client.send_statuscode("OK")

        # Process incoming packets until WebSocket closes
        try:
            async for packet in websocket:
                # Parse packet
                try:
                    packet: CloudlinkPacket = json.loads(packet)
                    if not isinstance(packet, dict):
                        cl_client.send_statuscode("Syntax")
                        continue
                    if "cmd" not in packet or "val" not in packet:
                        cl_client.send_statuscode("Syntax")
                        continue
                except:
                    cl_client.send_statuscode("Syntax")
                    continue

                if packet["cmd"] == "ping":
                    cl_client.send_statuscode("OK", packet.get("listener"))
                    continue

                if packet["cmd"] == "authpswd":
                    try:
                        # Make sure the client isn't already authenticated
                        if cl_client.username:
                            return cl_client.send_statuscode("OK", packet.get("listener"))
                        
                        # Check val datatype
                        if not isinstance(packet.get('val'), dict):
                            return cl_client.send_statuscode("Datatype", packet.get("listener"))
                        
                        # Check val values
                        if not packet.get("val").get("username") or not packet.get("val").get("pswd"):
                            return cl_client.send_statuscode("Syntax", packet.get("listener"))

                        account = db.usersv0.find_one({"tokens": packet.get("val").get("pswd")}, projection={"_id": 1})

                        if account:
                            cl_client.authenticate(security.get_account(account["_id"], include_config=True), used_token=packet.get("val").get("pswd"), listener=packet.get("listener"))
                        else:
                            cl_client.send_statuscode("PasswordInvalid")
                    except:
                        print(full_stack())
                        cl_client.send_statuscode("InternalServerError", packet.get("listener"))
                    continue

                cl_client.send_statuscode("Invalid", packet.get("listener"))
        except: pass
        finally:
            self.clients.remove(cl_client)
            cl_client.logout()

    def send_event(
        self,
        cmd: str,
        val: Any,
        extra: Optional[dict] = None,
        clients: Optional[Iterable] = None,
        usernames: Optional[Iterable] = None
    ):
        if extra is None:
            extra = {}

        # Get clients
        if clients is None and usernames is None:
            clients = self.clients
        else:
            clients = [] if clients is None else clients
            if usernames is not None:
                for username in usernames:
                    clients += self.usernames.get(username, [])

        # Parse post
        if cmd == "post" or cmd == "update_post":
            val = self.supporter.parse_posts_v0([val])[0]

        # Send v1 packet
        websockets.broadcast({
            client.websocket for client in clients
            if client.proto_version == 1
        }, json.dumps({"cmd": cmd, "val": val, **extra}))

        # Send v0 packet
        if cmd in ["statuscode", "ulist"]:  # root commands
            val = {"cmd": cmd, "val": val, **extra}
        else:
            if cmd == "post":
                if val.get("post_origin") == "home":
                    val = {"mode": 1, **val}
                else:
                    val = {"state": 2, **val}
            elif cmd == "typing":
                if val.get("chat_id") == "home":
                    val = {"state": 101, "chatid": "livechat", "u": val.get("username")}
                else:
                    val = {"state": 100, "chatid": val.get("chat_id"), "u": val.get("username")}
            elif cmd == "delete_chat":
                val = {"mode": "delete", "id": val.get("chat_id")}
            elif cmd == "delete_post":
                val = {"mode": "delete", "id": val.get("post_id")}
            else:
                val = {"mode": cmd, "payload": val}
            val = {"cmd": "direct", "val": val, **extra}
        websockets.broadcast({
            client.websocket for client in clients
            if client.proto_version == 0
        }, json.dumps(val))

    async def run(self, host: str = "0.0.0.0", port: int = 3000):
        self.stop = asyncio.Future()
        self.server = await websockets.serve(self.client_handler, host, port)
        await self.stop
        await self.server.close()

class CloudlinkClient:
    def __init__(
        self,
        server: CloudlinkServer,
        websocket: websockets.WebSocketServerProtocol
    ):
        # Set server and client objs
        self.server = server
        self.websocket = websocket

        # Set username, protocol version, and IP
        self.username: Optional[str] = None
        try:
            self.proto_version: int = int(self.req_params.get("v")[0])
        except:
            self.proto_version: int = 0
        
        self.ip: str = self.get_ip()

        # Automatic login
        if "token" in self.req_params:
            token = self.req_params.get("token")[0]
            account = self.proxy_api_request("/me", "get", headers={"token": token})
            if account:
                del account["error"]
                self.authenticate(account, token)

    @property
    def req_params(self):
        return parse_qs(urlparse(self.websocket.path).query)

    @property
    def ip(self):
        if "REAL_IP_HEADER" in os.environ and os.environ["REAL_IP_HEADER"] in self.websocket.request_headers:
            return self.websocket.request_headers[os.environ["REAL_IP_HEADER"]]
        elif type(self.websocket.remote_address) == tuple:
            return self.websocket.remote_address[0]
        else:
            return self.websocket.remote_address

    def authenticate(self, account: dict[str, Any], used_token: str, listener: Optional[str] = None):
        if self.username:
            self.logout()

        # Check ban
        if (account["ban"]["state"] == "perm_ban") or (account["ban"]["state"] == "temp_ban" and account["ban"]["expires"] > time.time()):
            self.send("banned", account["ban"], listener=listener)
            return self.send_statuscode("Banned", listener)

        # Authenticate
        self.username = account["_id"]

        if not self.username in self.server.usernames:
            self.server.usernames[self.username] = []
            self.server.send_event("ulist", self.server.get_ulist())
        
        self.server.usernames[self.username].append(self)

        # Send auth payload
        self.send("auth", {
            "username": self.username,
            "token": used_token,
            "account": account,
            "relationships": self.proxy_api_request("/me/relationships", "get")["autoget"],
            **({
                "chats": self.proxy_api_request("/chats", "get")["autoget"]
            } if self.proto_version != 0 else {})
        }, listener=listener)

    def logout(self):
        if not self.username:
            return

        # Trigger last_seen update
        self.proxy_api_request("/me", "get")

        self.server.usernames[self.username].remove(self)
        if len(self.server.usernames[self.username]) == 0:
            del self.server.usernames[self.username]
            self.server.send_event('ulist', self.server.get_ulist())
        self.username = None

   def send(self, cmd: str, val: Any, extra: Optional[dict] = None, listener: Optional[str] = None):
        if extra is None:
            extra = {}
        if listener:
            extra["listener"] = listener
        return self.server.send_event(cmd, val, extra=extra, clients=[self])

    def send_statuscode(self, statuscode: str, listener: Optional[str] = None):
        return self.send("statuscode", self.server.statuscodes[statuscode], listener=listener)

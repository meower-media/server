import websockets, asyncio, json, time, requests, os
from typing import Optional, Iterable, TypedDict, Literal, Any
from inspect import getfullargspec
from urllib.parse import urlparse, parse_qs

from utils import log, full_stack

VERSION = "0.1.7.9"

class CloudlinkPacket(TypedDict):
    cmd: str
    val: any
    id: Optional[str]
    name: Optional[str]
    origin: Optional[str]
    listener: Optional[str]

class CloudlinkServer:
    def __init__(self):
        self.statuscodes: dict[str, str] = {
            #"Test": "I:000 | Test", -- unused
            "OK": "I:100 | OK",
            "Syntax": "E:101 | Syntax",
            "Datatype": "E:102 | Datatype",
            "IDNotFound": "E:103 | ID not found",
            "InternalServerError": "E:104 | Internal",
            #"Loop": "E:105 | Loop detected",  -- deprecated
            "RateLimit": "E:106 | Too many requests",
            #"TooLarge": "E:107 | Packet too large",  -- deprecated
            #"BrokenPipe": "E:108 | Broken pipe",  -- deprecated
            #"EmptyPacket": "E:109 | Empty packet",  -- unused
            #"IDConflict": "E:110 | ID conflict",  -- deprecated
            #"IDSet": "E:111 | ID already set",  -- deprecated
            "TAEnabled": "I:112 | Trusted Access enabled",
            #"TAInvalid": "E:113 | TA Key invalid",  -- deprecated
            #"TAExpired": "E:114 | TA Key expired",  -- deprecated
            #"Refused": "E:115 | Refused",  -- deprecated
            "IDRequired": "E:116 | Username required",
            #"TALostTrust": "E:117 | Trust lost",  -- deprecated
            "Invalid": "E:118 | Invalid command",
            "Blocked": "E:119 | IP Blocked",
            #"IPRequred": "E:120 | IP Address required",  -- deprecated
            #"TooManyUserNameChanges": "E:121 | Too Many Username Changes",  -- deprecated
            #"Disabled": "E:122 | Command disabled by sysadmin",  -- deprecated
            "PasswordInvalid": "I:011 | Invalid Password",
            "IDExists": "I:015 | Account exists",
            "2FARequired": "I:016 | 2FA Required",
            #"MissingPermissions": "I:017 | Missing permissions",  -- deprecated
            "Banned": "E:018 | Account Banned",
            #"IllegalChars": "E:019 | Illegal characters detected",  -- deprecated
            #"Kicked": "E:020 | Kicked",  -- deprecated
            #"ChatFull": "E:023 | Chat full",  -- deprecated
            #"LoggedOut": "I:024 | Logged out",  -- deprecated
            "Deleted": "E:025 | Deleted"
        }
        self.commands: dict[str, function] = {
            # Core commands
            "ping": CloudlinkCommands.ping,
            "get_ulist": CloudlinkCommands.get_ulist,
            "pmsg": CloudlinkCommands.pmsg,
            "pvar": CloudlinkCommands.pvar,

            # Authentication
            "authpswd": CloudlinkCommands.authpswd,
            "gen_account": CloudlinkCommands.gen_account,

            # Accounts
            "update_config": CloudlinkCommands.update_config,
            "change_pswd": CloudlinkCommands.change_pswd,
            "del_tokens": CloudlinkCommands.del_tokens,
            "del_account": CloudlinkCommands.del_account,

            # Moderation
            "report": CloudlinkCommands.report
        }
        self.clients: set[CloudlinkClient] = set()
        self.usernames: dict[str, list[CloudlinkClient]] = {}  # {"username": [cl_client1, cl_client2, ...]}
    
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
        else:
            cl_client.trusted = True

        # Process incoming packets until WebSocket closes
        try:
            async for packet in websocket:
                # Parse packet
                try:
                    packet: CloudlinkPacket = json.loads(packet)
                except:
                    cl_client.send_statuscode("Syntax")
                    continue
                else:
                    if not isinstance(packet, dict):
                        cl_client.send_statuscode("Syntax")
                        continue

                # Make sure the packet includes `cmd` and `val`
                if "cmd" not in packet or "val" not in packet:
                    cl_client.send_statuscode("Syntax", packet.get("listener"))
                    continue

                # Pseudo Trusted Access
                if not cl_client.trusted and packet["cmd"] in ["direct", "gmsg"]:
                    if isinstance(packet["val"], str):
                        cl_client.trusted = True
                        cl_client.send_statuscode("OK", packet.get("listener"))
                        continue

                # Unwrap "direct" cmd
                if packet["cmd"] == "direct" and isinstance(packet["val"], dict):
                    packet["cmd"] = packet["val"].get("cmd")
                    if not packet["cmd"]:
                        cl_client.send_statuscode("Syntax", packet.get("listener"))
                        continue
                    elif packet["cmd"] == "type":
                        continue

                    packet["val"] = packet["val"].get("val")
                    if packet["val"] is None:
                        cl_client.send_statuscode("Syntax", packet.get("listener"))
                        continue

                # Get command function
                cmd_func = self.commands.get(packet["cmd"])
                if not cmd_func:
                    cl_client.send_statuscode("Invalid", packet.get("listener"))
                    continue

                # Execute command
                try:
                    # Extra args mainly used for pmsg, gvar, and pvar
                    extra_args = {}
                    if "id" in getfullargspec(cmd_func).args:
                        extra_args["id"] = packet.get("id")
                    if "name" in getfullargspec(cmd_func).args:
                        extra_args["name"] = packet.get("name")
                    
                    await cmd_func(cl_client, packet["val"], packet.get("listener"), **extra_args)
                except:
                    print(full_stack())
                    cl_client.send_statuscode("InternalServerError", packet.get("listener"))
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
        if cmd in ["statuscode", "ulist", "pmsg", "pvar"]:  # root commands
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

    def get_ulist(self):
        ulist = ";".join(self.usernames.keys())
        if ulist:
            ulist += ";"
        return ulist

    def send_ulist(self):
        return self.send_event("ulist", self.get_ulist())

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

        # Set username, protocol version, IP, and trusted status
        self.username: Optional[str] = None
        try:
            self.proto_version: int = int(self.req_params.get("v")[0])
        except:
            self.proto_version: int = 0
        self.trusted: bool = False

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

    def authenticate(self, account: dict[str, Any], token: str, listener: Optional[str] = None):
        if self.username:
            self.logout()

        # Check ban
        if (account["ban"]["state"] == "perm_ban") or (account["ban"]["state"] == "temp_ban" and account["ban"]["expires"] > time.time()):
            self.send("banned", account["ban"], listener=listener)
            return self.send_statuscode("Banned", listener)

        # Authenticate
        self.username = account["_id"]
        if self.username in self.server.usernames:
            self.server.usernames[self.username].append(self)
        else:
            self.server.usernames[self.username] = [self]
            self.server.send_ulist()

        # Send auth payload
        self.send("auth", {
            "username": self.username,
            "token": token,
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
            self.server.send_ulist()
        self.username = None

    def proxy_api_request(
        self, endpoint: str,
        method: Literal["get", "post", "patch", "delete"],
        headers: dict[str, str] = {},
        json: Optional[dict[str, Any]] = None,
        listener: Optional[str] = None,
    ):
        # Set headers
        headers.update({
            "X-Internal-Token": os.environ["INTERNAL_API_TOKEN"],
            "X-Internal-Ip": self.ip,
        })
        if self.username:
            headers["X-Internal-Username"] = self.username

        # Make request
        resp = getattr(requests, method)(
            f"{os.environ['INTERNAL_API_ENDPOINT']}{endpoint}",
            headers=headers,
            json=json,
        ).json()
        if not resp["error"]:
            return resp
        else:
            match resp["type"]:
                case "repairModeEnabled":
                    self.kick()
                case "ipBlocked"|"registrationBlocked":
                    self.send_statuscode("Blocked", listener)
                case "badRequest":
                    self.send_statuscode("Syntax", listener)
                case "usernameExists":
                    self.send_statuscode("IDExists", listener)
                case "Unauthorized":
                    self.send_statuscode("PasswordInvalid", listener)
                case "mfaRequired":
                    self.send_statuscode("2FARequired", listener)
                case "accountDeleted":
                    self.send_statuscode("Deleted", listener)
                case "accountBanned":
                    self.send_statuscode("Banned", listener)
                case "tooManyRequests":
                    self.send_statuscode("RateLimit", listener)
                case _:
                    log(f"Unknown error type received from '{endpoint}' API endpoint: {resp['type']}")
                    self.send_statuscode("InternalServerError", listener)

    def send(self, cmd: str, val: Any, extra: Optional[dict] = None, listener: Optional[str] = None):
        if extra is None:
            extra = {}
        if listener:
            extra["listener"] = listener
        return self.server.send_event(cmd, val, extra=extra, clients=[self])

    def send_statuscode(self, statuscode: str, listener: Optional[str] = None):
        return self.send("statuscode", self.server.statuscodes[statuscode], listener=listener)

    def kick(self):
        async def _kick():
            await self.websocket.close()
        asyncio.create_task(_kick())

class CloudlinkCommands:
    @staticmethod
    async def ping(client: CloudlinkClient, val, listener: Optional[str] = None):
        client.send_statuscode("OK", listener)
    
    @staticmethod
    async def get_ulist(client: CloudlinkClient, val, listener: Optional[str] = None):
        client.send("ulist", client.server.get_ulist(), listener=listener)

    @staticmethod
    async def pmsg(client: CloudlinkClient, val, listener: Optional[str] = None, id: Optional[str] = None):
        if not client.username:
            client.send_statuscode("IDRequired", listener)
            return
        if id not in client.server.usernames:
            client.send_statuscode("IDNotFound", listener)
            return
        
        client.server.send_event("pmsg", val, extra={"origin": client.username}, usernames=[id])
        client.send_statuscode("OK", listener)

    @staticmethod
    async def pvar(client: CloudlinkClient, val, listener: Optional[str] = None, id: Optional[str] = None, name: Optional[str] = None):
        if not client.username:
            client.send_statuscode("IDRequired", listener)
            return
        if id not in client.server.usernames:
            client.send_statuscode("IDNotFound", listener)
            return
        
        client.server.send_event("pvar", val, extra={"origin": client.username, "name": name}, usernames=[id])
        client.send_statuscode("OK", listener)

    @staticmethod
    async def authpswd(client: CloudlinkClient, val, listener: Optional[str] = None):
        # Make sure the client isn't already authenticated
        if client.username:
            return client.send_statuscode("OK", listener)
        
        # Check val datatype
        if not isinstance(val, dict):
            return client.send_statuscode("Datatype", listener)

        # Send API request
        try:
            resp = client.proxy_api_request("/auth/login", "post", json={
                "username": val.get("username"),
                "password": val.get("pswd"),
            }, listener=listener)
        except:
            print(full_stack())
            client.send_statuscode("InternalServerError", listener)
        else:
            if resp and not resp["error"]:
                # Authenticate client
                client.authenticate(resp["account"], resp["token"], listener=listener)
                
                # Tell the client it is authenticated
                client.send_statuscode("OK", listener)

    @staticmethod
    async def gen_account(client: CloudlinkClient, val, listener: Optional[str] = None):
        # Make sure the client isn't already authenticated
        if client.username:
            return client.send_statuscode("OK", listener)
        
        # Check val datatype
        if not isinstance(val, dict):
            return client.send_statuscode("Datatype", listener)

        # Send API request
        try:
            resp = client.proxy_api_request("/auth/register", "post", json={
                "username": val.get("username"),
                "password": val.get("pswd"),
            }, listener=listener)
        except:
            print(full_stack())
            client.send_statuscode("InternalServerError", listener)
        else:
            if resp and not resp["error"]:
                # Authenticate client
                client.authenticate(resp["account"], resp["token"], listener=listener)
                
                # Tell the client it is authenticated
                client.send_statuscode("OK", listener)

    @staticmethod
    async def update_config(client: CloudlinkClient, val, listener: Optional[str] = None):
        # Make sure the client is authenticated
        if not client.username:
            return client.send_statuscode("IDRequired", listener)
        
        # Check val datatype
        if not isinstance(val, dict):
            return client.send_statuscode("Datatype", listener)

        # Send API request
        try:
            resp = client.proxy_api_request("/me/config", "post", json=val, listener=listener)
        except:
            print(full_stack())
            client.send_statuscode("InternalServerError", listener)
        else:
            if resp and not resp["error"]:
                client.send_statuscode("OK", listener)

    @staticmethod
    async def change_pswd(client: CloudlinkClient, val, listener: Optional[str] = None):
        # Make sure the client is authenticated
        if not client.username:
            return client.send_statuscode("IDRequired", listener)

        # Check val datatype
        if not isinstance(val, dict):
            return client.send_statuscode("Datatype", listener)

        # Send API request
        try:
            resp = client.proxy_api_request("/me/password", "patch", json=val, listener=listener)
        except:
            print(full_stack())
            client.send_statuscode("InternalServerError", listener)
        else:
            if resp and not resp["error"]:
                client.send_statuscode("OK", listener)

    @staticmethod
    async def del_tokens(client: CloudlinkClient, val, listener: Optional[str] = None):
        # Make sure the client is authenticated
        if not client.username:
            return client.send_statuscode("IDRequired", listener)

        # Send API request
        try:
            resp = client.proxy_api_request("/me/tokens", "delete", listener=listener)
        except:
            print(full_stack())
            client.send_statuscode("InternalServerError", listener)
        else:
            if resp and not resp["error"]:
                client.send_statuscode("OK", listener)

    @staticmethod
    async def del_account(client: CloudlinkClient, val, listener: Optional[str] = None):
        # Make sure the client is authenticated
        if not client.username:
            return client.send_statuscode("IDRequired", listener)
        
        # Check val datatype
        if not isinstance(val, str):
            return client.send_statuscode("Datatype", listener)

        # Send API request
        try:
            resp = client.proxy_api_request("/me", "delete", json={"password": val}, listener=listener)
        except:
            print(full_stack())
            client.send_statuscode("InternalServerError", listener)
        else:
            if resp and not resp["error"]:
                client.send_statuscode("OK", listener)

    @staticmethod
    async def report(client: CloudlinkClient, val, listener: Optional[str] = None):
        # Make sure the client is authenticated
        if not client.username:
            return client.send_statuscode("IDRequired", listener)
        
        # Check val datatype
        if not isinstance(val, str):
            return client.send_statuscode("Datatype", listener)

        # Get endpoint
        if val.get("type") == 0:
            endpoint = f"/posts/{val.get('id')}/report"
        elif val.get("type") == 1:
            endpoint = f"/users/{val.get('id')}/report"
        else:
            return client.send_statuscode("Datatype", listener)

        # Send API request
        try:
            resp = client.proxy_api_request(endpoint, "post", json={
                "reason": val.get("reason"),
                "comment": val.get("comment"),
            }, listener=listener)
        except:
            print(full_stack())
            client.send_statuscode("InternalServerError", listener)
        else:
            if resp and not resp["error"]:
                client.send_statuscode("OK", listener)

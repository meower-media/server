import websockets
import asyncio
import json

from src.cl3.commands import CL3Commands

VERSION = "0.1.7.7"
CODES = {
    "InvalidPassword": "I:011 | Invalid Password",
    "2FAOnly": "I:016 | 2FA Required",
    "MissingPermissions": "I:017 | Missing permissions",
    "Banned": "E:018 | Account Banned",
    "IllegalChars": "E:019 | Illegal characters detected",
    "Kicked": "E:020 | Kicked",
    "OK": "I:100 | OK",
    "Syntax": "E:101 | Syntax",
    "Datatype": "E:102 | Datatype",
    "IDNotFound": "E:103 | ID not found",
    "Internal": "E:104 | Internal",
    "Loop": "E:105 | Loop detected",
    "RateLimit": "E:106 | Too many requests",
    "TooLarge": "E:107 | Packet too large",
    "IDConflict": "E:110 | ID conflict",
    "Disabled": "E:122 | Command disabled by sysadmin"
}
COMMANDS = {
    "ping",
    "version_chk",
    "get_ulist",
    "authpswd",
    "get_profile",
    "get_home",
    "post_home",
    "get_post",
    "search_user_posts",
    "delete_post"
}
DISABLED_COMMANDS = {
    "gmsg",
    "gvar"
}

class server:
    def __init__(self):
        self.clients = set()
        self._user_ids = {}
        self._usernames = {}
        self._chats = {}

        self.command_handler = CL3Commands(self)

    @property
    def ulist(self):
        if len(self.clients) == 0:
            return ""
        else:
            _ulist = ""
            for username in list(self._usernames.keys()):
                _ulist += f"{username};"
            return _ulist

    async def broadcast(self, payload: dict):
        for client in self.clients:
            try:
                await client.send(json.dumps(payload))
            except:
                pass

    async def send_to_client(self, client, payload: dict, listener: str = None):
        if listener:
            payload["listener"] = listener
        try:
            await client.send(json.dumps(payload))
        except:
            pass
    
    async def send_code(self, client, code: str, listener: str = None):
        payload = {"cmd": "statuscode", "val": CODES[code]}
        if listener:
            payload["listener"] = listener
        await client.send(json.dumps(payload))

    async def kick_client(self, client, code: str = None):
        if code:
            await self.send_to_client(client, {"cmd": "direct", "val": CODES[code]})
        await client.close(code=1001, reason="")

    async def __handler__(self, client):
        client.user_id = None
        client.username = None
        self.clients.add(client)
        await self.send_to_client(client, {"cmd": "ulist", "val": self.ulist})
        try:
            async for message in client:
                if len(message) > 1000:
                    await self.send_code(client, "TooLarge")
                try:
                    # Unpackage command
                    if ("cmd" not in message) or ("val" not in message):
                        await self.send_code(client, "Syntax")
                    message = json.loads(message)
                    listener = message.get("listener")
                    if message["cmd"] == "direct":
                        if isinstance(message["val"], str):
                            await self.send_code(client, "OK", listener)
                        message = message["val"]
                    cmd = message["cmd"]
                    val = message["val"]

                    # Run command
                    if cmd in DISABLED_COMMANDS:
                        await self.send_code(client, "Disabled", listener=listener)
                    elif (cmd in COMMANDS) and (hasattr(self.command_handler, cmd)):
                        try:
                            await getattr(self.command_handler, cmd)(client, val, listener)
                        except Exception as e:
                            print(e)
                            await self.send_code(client, "Internal", listener=listener)
                    else:
                        await self.send_code(client, "Invalid")
                except:
                    await self.send_code(client, "Syntax")
        except:
            pass
        finally:
            self.clients.remove(client)
            if client.user_id in self._user_ids:
                del self._user_ids[client.user_id]
            if client.username in self._usernames:
                del self._usernames[client.username]
                await self.broadcast({"cmd": "ulist", "val": self.ulist})

            del client

    async def main(self, host="localhost", port=3002):
        async with websockets.serve(self.__handler__, host, port):
            await asyncio.Future()

# Initialize the CL server
cl = server()

# Initialize the event handler
from src.cl3 import events
cl._event_handler = events

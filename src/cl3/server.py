from copy import copy
import websockets
import asyncio
import ujson

from src.cl3.events import CL3Events
from src.cl3.commands import CL3Commands
from src.common.entities import networks
from src.common.util import config, full_stack, uid
from src.common.database import redis


VERSION = "0.1.7.7"
CODES = {
    "InvalidPassword": "I:011 | Invalid Password",
    "IDExists": "I:015 | Account exists",
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
    "Ratelimited": "E:106 | Too many requests",
    "TooLarge": "E:107 | Packet too large",
    "IDRequired": "E:116 | Username required",
    "Invalid": "E:118 | Invalid command",
    "IPBanned": "E:119 | IP Blocked",
    "Disabled": "E:122 | Command disabled by sysadmin"
}
COMMANDS = {
    "ip",
    "type",
    "direct",
    "setid",
    "pmsg",
    "pvar",
    "ping",
    "version_chk",
    "get_ulist",
    "get_peak_users",
    "authpswd",
    "gen_account",
    "get_profile",
    "update_config",
    "change_pswd",
    "del_tokens",
    "del_account",
    "get_inbox",
    "get_home",
    "post_home",
    "get_post",
    "delete_post",
    "search_user_posts",
    "report",
    "close_report",
    "clear_home",
    "clear_user_posts",
    "get_user_data",
    "alert",
    "kick",
    "ban",
    "pardon",
    "terminate",
    "gdpr",
    "get_ip_data",
    "block",
    "unblock",
    "get_user_ip",
    "ip_ban",
    "ip_pardon",
    "announce",
    "repair_mode",
    "get_chat_list",
    "create_chat",
    "join_chat",
    "leave_chat",
    "get_chat_data",
    "edit_chat",
    "delete_chat",
    "add_to_chat",
    "remove_from_chat",
    "set_chat_state",
    "get_chat_posts",
    "post_chat"
}
DISABLED_COMMANDS = {
    "gmsg",
    "gvar"
}


class server:
    def __init__(self):
        self.clients = set()
        self.users = {}
        self.invisible_users = set()
        self.chats = {}
        self.peak_users = {}

        self.events_handler = CL3Events(self)
        self.command_handler = CL3Commands(self)

    @property
    def ulist(self):
        _ulist = ""
        for username in self.users.keys():
            if username not in self.invisible_users:
                _ulist += f"{username};"
        return _ulist

    async def broadcast(self, payload: dict):
        payload = ujson.dumps(payload)
        for client in copy(self.clients):
            try:
                await client.send(payload)
            except:
                pass

    async def send_to_client(self, client, payload: dict, listener: str = None):
        if listener:
            payload["listener"] = listener
        try:
            await client.send(ujson.dumps(payload))
        except:
            pass

    async def send_to_user(self, username: str, payload: dict):
        payload = ujson.dumps(payload)
        for client in copy(self.users.get(username, set())):
            try:
                await client.send(payload)
            except:
                pass
    
    async def send_to_chat(self, chat_id: str, payload: dict):
        payload = ujson.dumps(payload)
        for client in copy(self.chats.get(chat_id, set())):
            try:
                await client.send(payload)
            except:
                pass

    async def send_code(self, client, code: str, listener: str = None):
        payload = {"cmd": "statuscode", "val": CODES[code]}
        if listener:
            payload["listener"] = listener
        await client.send(ujson.dumps(payload))

    async def log_peak_users(self):
        if len(self.users.keys()) > self.peak_users.get("count", 0):
            self.peak_users = {
                "count": len(self.users.keys()),
                "timestamp": uid.timestamp(jsonify=True)
            }
            await self.broadcast({
                "cmd": "direct",
                "val": {
                    "mode": "peak",
                    "payload": self.peak_users
                }
            })

    def subscribe_to_chat(self, client, chat_id: str):
        if chat_id not in self.chats:
            self.chats[chat_id] = set()
        self.chats[chat_id].add(client)
        client.chats.add(chat_id)

    def unsubscribe_from_chat(self, client, chat_id: str):
        if client in self.chats.get(chat_id, set()):
            self.chats[chat_id].remove(client)
            if len(self.chats[chat_id]) == 0:
                del self.chats[chat_id]

    async def kick_client(self, client, code: str = None):
        if code:
            await self.send_to_client(client, {"cmd": "direct", "val": CODES[code]})
        await client.close(code=1001, reason="")

    async def __handler__(self, client):
        # Check whether repair mode is enabled
        if redis.exists("repair_mode") == 1:
            return await self.kick_client(client)

        # Get client's IP address
        if config.ip_header and (config.ip_header in client.request_headers):
            client.ip = client.request_headers[config.ip_header]
        else:
            if isinstance(client.remote_address, tuple):
                client.ip = str(client.remote_address[0])
            else:
                client.ip = client.remote_address

        # Check whether network is banned
        network = networks.get_network(client.ip)
        if network.banned:
            return await self.kick_client(client, code="IPBanned")

        # Assign client properties and add to clients list
        client.username = None
        client.chats = set()
        self.clients.add(client)

        # Subscribe client to livechat
        self.subscribe_to_chat(client, "livechat")

        # Send current ulist to client
        await self.send_to_client(client, {"cmd": "ulist", "val": self.ulist})

        try:
            # Handle incoming commands from the client
            async for message in client:
                # Check message size
                if len(message) > 5000:
                    await self.send_code(client, "TooLarge")
                    continue

                try:
                    # Parse message
                    try:
                        message = ujson.loads(message)
                    except ujson.JSONDecodeError:
                        await self.send_code(client, "Datatype")
                        continue
                    
                    # Extract data
                    try:
                        cmd = message["cmd"]
                        val = message["val"]
                        listener = message.get("listener")
                    except KeyError:
                        await self.send_code(client, "Syntax")
                        continue

                    # Convert direct command
                    if (cmd == "direct") and isinstance(val, dict) and ("cmd" in val) and ("val" in val):
                        cmd = val["cmd"]
                        val = val["val"]

                    # Convert val for pmsg/pvar
                    if (cmd == "pmsg") or (cmd == "pvar"):
                        val = message

                    # Check if command exists
                    if (cmd not in COMMANDS) or (not hasattr(self.command_handler, cmd)):
                        await self.send_code(client, "Invalid", listener=listener)
                        continue

                    # Check if command is disabled
                    if cmd in DISABLED_COMMANDS:
                        await self.send_code(client, "Disabled", listener=listener)
                        continue

                    # Run command
                    await getattr(self.command_handler, cmd)(client, val, listener)

                    # Send OK statuscode
                    await self.send_code(client, "OK", listener)
                except Exception as e:
                    if hasattr(e, "cl_code"):
                        await self.send_code(client, e.cl_code, listener=listener)
                        continue
                    else:
                        if config.development:
                            print(full_stack())
                        await self.send_code(client, "Internal", listener=listener)
                        continue
        except:
            if config.development:
                print(full_stack())
        finally:
            # Remove client from clients list
            self.clients.remove(client)

            # Remove client from users object
            if client.username in self.users:
                self.users[client.username].remove(client)
                if len(self.users[client.username]) == 0:
                    del self.users[client.username]
                await self.broadcast({"cmd": "ulist", "val": self.ulist})

            # Unsubscribe client from all chats
            for chat_id in client.chats:
                self.unsubscribe_from_chat(client, chat_id)

            # Remove username from invisible users list
            if (client.username in self.invisible_users) and (len(self.users.get(client.username, set())) == 0):
                self.invisible_users.remove(client.username)

    async def main(self, host="localhost", port=3000):
        async with websockets.serve(self.__handler__, host, port):
            await asyncio.Future()


# Initialize the CL server
cl = server()

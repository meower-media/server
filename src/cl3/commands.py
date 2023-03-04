import time
import uuid
import secrets
import pymongo
import os
import requests
import asyncio

from src.util import status
from src.entities import users, accounts, networks, sessions, infractions, posts

class CL3Commands:
    def __init__(self, cl_server):
        self.cl = cl_server
    
    # Networking/client utilities
    
    async def ping(self, client, val, listener):
        await self.cl.send_code(client, "OK", listener)
    
    async def version_chk(self, client, val, listener):
        await self.cl.send_code(client, "OK", listener)
    
    async def get_ulist(self, client, val, listener):
        await self.cl.send_to_client(client, {"cmd": "ulist", "val": self.cl.ulist}, listener)

    # Accounts and security
    
    async def authpswd(self, client, val, listener):
        # Check if the client is already authenticated
        if client.user_id:
            return await self.cl.send_code(client, "OK", listener)
        
        # Check syntax
        if not isinstance(val, dict):
            return await self.cl.send_code(client, "Datatype", listener)
        elif ("username" not in val) or ("pswd" not in val):
            return await self.cl.send_code(client, "Syntax", listener)
        
        # Extract username and password
        username = val["username"]
        password = val["pswd"]

        # Check datatype
        if not (isinstance(username, str) and isinstance(password, str)):
            return await self.cl.send_code(client, "Datatype", listener)
        
        # Get user and account
        try:
            user_id = users.get_id_from_username(username)
            user = users.get_user(user_id, return_deleted=False)
            account = accounts.get_account(user_id)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)
        
        # Check whether account can MFA enabled
        if account.mfa_enabled:
            return await self.cl.send_code(client, "2FAOnly", listener)
        
        # Check account password
        if account.locked:
            return await self.cl.send_code(client, "RateLimit", listener)
        elif not account.check_password(password):
            return await self.cl.send_code(client, "InvalidPassword", listener)
        
        # Check whether user is banned
        moderation_status = infractions.user_status(user)
        if moderation_status["banned"]:
            return await self.cl.send_code(client, "Banned", listener)

        # Authenticate client
        if user.id in self.cl._user_ids:
            await self.cl.kick_client(self.cl._user_ids[user.id], "IDConflict")
        client.user_id = user.id
        client.username = username
        self.cl._user_ids[user.id] = client
        self.cl._usernames[username] = client
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "auth",
                "payload": {
                    "username": username,
                    "token": "abc"
                }
            }
        }
        await self.cl.broadcast({"cmd": "ulist", "val": self.cl.ulist})
        await self.cl.send_to_client(client, payload, listener)
        return await self.cl.send_code(client, "OK", listener)
    
    async def get_profile(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)

        # Check datatype
        if not isinstance(val, str):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get user
        try:
            user_id = users.get_id_from_username(val)
            user = users.get_user(user_id, return_deleted=False)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)
        except:
            return await self.cl.send_code(client, "Internal", listener)
        
        # Return user
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "profile",
                "payload": (user.legacy_client if (client.user_id == user.id) else user.legacy_public),
                "user_id": user.id
            }
        }
        await self.cl.send_to_client(client, payload, listener)
        return await self.cl.send_code(client, "OK", listener)
    
    async def update_config(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, dict):
            return await self.cl.send_code(client, "Datatype", listener)

        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                FileCheck, FileRead, Payload = self.accounts.get_account(client, True, True)
                if FileCheck and FileRead:
                    self.log("{0} updating config".format(client))
                    FileCheck, FileRead, FileWrite = self.accounts.update_setting(client, val)
                    if FileCheck and FileRead and FileWrite:
                        # OK
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # raise an internal error.
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    if ((not FileCheck) and FileRead):
                        # Account not found
                        self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Some other error, raise an internal error.
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    # General
    
    async def get_home(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Get page
        if isinstance(val, dict) and ("page" in val) and isinstance(val["page"], int):
            page = val["page"]
        else:
            page = 1

        # Get home index
        home_index = [post.id for post in posts.get_latest_posts()]

        # Return home index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "home",
                "payload": home_index
            }
        }
        await self.cl.send_code(client, "OK", listener)
        return await self.cl.send_to_client(client, payload, listener)
    
    async def post_home(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check syntax
        if not isinstance(val, str):
            return await self.cl.send_code(client, "Datatype", listener)
        elif len(val) > 360:
            return await self.cl.send_code(client, "TooLarge", listener)
        
        # Get user
        user = users.get_user(client.user_id, return_deleted=False)

        # Check whether the user is suspended
        moderation_status = infractions.user_status(user)
        if moderation_status["suspended"] or moderation_status["banned"]:
            return await self.cl.send_code(client, "Banned", listener)

        # Create post
        posts.create_post(user, val)

        # Tell the client the post was created
        return await self.cl.send_code(client, "OK", listener)
    
    async def get_post(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, str):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get post
        try:
            post = posts.get_post(val, error_on_deleted=True)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)
        
        # Return post
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "post",
                "payload": post.legacy_public
            }
        }
        await self.cl.send_to_client(client, payload, listener)
        return await self.cl.send_code(client, "OK", listener)
    
    # Logging and data management
    
    def get_peak_users(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            payload = {
                "mode": "peak",
                "payload": self.supporter.peak_users_logger
            }
            
            # Relay data to client
            self.sendPacket({"cmd": "direct", "val": payload, "id": client})
            
            # Tell client data was sent
            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def search_user_posts(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if ("query" in val) and (type(val["query"]) == str):
                    if ("page" in val) and self.checkForInt(val["page"]):
                        page = int(val["page"])
                    else:
                        page = 1

                    post_index = self.getIndex(location="posts", query={"post_origin": "home", "u": val["query"], "isDeleted": False}, truncate=True, page=page)
                    for i in range(len(post_index["index"])):
                        post_index["index"][i] = post_index["index"][i]["_id"]
                    post_index["index"].reverse()
                    payload = {
                        "mode": "user_posts",
                        "index": post_index
                    }
                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Bad syntax
                    self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    # Moderator features
    
    def report(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if ("type" in val) and ("id" in val):
                    if (type(val["type"]) == int) and (type(val["id"]) == str):
                        if val["type"] == 0:
                            if not self.filesystem.does_item_exist("posts", val["id"]):
                                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                        elif val["type"] == 1:
                            if not self.filesystem.does_item_exist("usersv0", val["id"]):
                                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
                        
                        if self.filesystem.does_item_exist("reports", val["id"]):
                            FileRead, reportData = self.filesystem.load_item("reports", val["id"])
                            if FileRead:
                                if client not in reportData["reports"]:
                                    reportData["reports"].append(client)
                                    FileWrite = self.filesystem.write_item("reports", val["id"], reportData)
                                    if FileWrite:
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            FileWrite = self.filesystem.create_item("reports", val["id"], {"type": val["type"], "reports": [client]})
                            if FileWrite:
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Bad syntax
                    self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    # Chat-related
    
    async def delete_post(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, str):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get post
        try:
            post = posts.get_post(val, error_on_deleted=True)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)
        
        # Check whether the client owns the post
        if client.user_id != post.author.id:
            return await self.cl.send_code(client, "Refused", listener)

        # Delete the post
        post.delete()

        # Tell the client the post was deleted
        return await self.cl.send_code(client, "OK", listener)
    
    def create_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 20:
                    val = self.supporter.wordfilter(val)
                    if not self.filesystem.does_item_exist("chats", val):
                        result = self.filesystem.create_item("chats", str(uuid.uuid4()), {"nickname": val, "owner": client, "members": [client]})
                        if result:
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        self.returnCode(client = client, code = "ChatExists", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Bad syntax
                    self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def leave_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 50:
                    if self.filesystem.does_item_exist("chats", val):
                        result, payload = self.filesystem.load_item("chats", val)
                        if result:
                            if client in payload["members"]:
                                if payload["owner"] == client:
                                    result = self.filesystem.delete_item("chats", val)
                                    for member in payload["members"]:
                                        if member in self.cl.getUsernames():
                                            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": payload["_id"]}, "id": member})
                                    if result:
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    payload["members"].remove(client)
                                    result = self.filesystem.write_item("chats", val, payload)
                                    if result:
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Too large
                    self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def get_chat_list(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if (type(val) == dict) and ("page" in val) and self.checkForInt(val["page"]):
                page = int(val["page"])
            else:
                page = 1
            chat_index = self.getIndex(location="chats", query={"members": {"$all": [client]}}, truncate=True, page=page, sort="nickname")
            chat_index["all_chats"] = []
            for i in range(len(chat_index["index"])):
                chat_index["all_chats"].append(chat_index["index"][i])
                chat_index["index"][i] = chat_index["index"][i]["_id"]
            chat_index["index"].reverse()
            chat_index["all_chats"].reverse()
            payload = {
                "mode": "chats",
                "payload": chat_index
            }
            self.sendPacket({"cmd": "direct", "val": payload, "id": client})
            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def get_chat_data(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 50:
                    if self.filesystem.does_item_exist("chats", val):
                        result, chatdata = self.filesystem.load_item("chats", val)
                        if result:
                            if client in chatdata["members"]:
                                payload = {
                                    "mode": "chat_data",
                                    "payload": {
                                        "chatid": chatdata["_id"],
                                        "nickname": chatdata["nickname"],
                                        "owner": chatdata["owner"],
                                        "members": chatdata["members"]
                                    }
                                }
                                self.sendPacket({"cmd": "direct", "val": payload, "id": client})
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def get_chat_posts(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 50:
                    if self.filesystem.does_item_exist("chats", val):
                        result, chatdata = self.filesystem.load_item("chats", val)
                        if result:
                            if client in chatdata["members"]:
                                posts_index = self.getIndex(location="posts", query={"post_origin": val, "isDeleted": False}, truncate=True)
                                for i in range(len(posts_index["index"])):
                                    posts_index["index"][i] = posts_index["index"][i]["_id"]
                                print(posts_index)
                                payload = {
                                    "mode": "chat_posts",
                                    "payload": posts_index
                                }
                                self.sendPacket({"cmd": "direct", "val": payload, "id": client})
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            
                            else:
                                self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    # Formatting looks different to other commands because this is taken from the beta 6 server
    def set_chat_state(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            # Not authenticated
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        elif not ((type(val) == dict) and (("state" in val) and self.checkForInt(val["state"]) and (("chatid" in val) and (type(val["chatid"]) == str)))):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif len(val["chatid"]) > 50:
            # Chat ID too long
            return self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract state and chat ID for simplicity
        state = int(val["state"])
        chatid = val["chatid"]

        # Some messy permission checking
        if chatid == "livechat":
            pass
        else:
            FileRead, chatdata = self.filesystem.load_item("chats", chatid)
            if not FileRead:
                if not self.filesystem.does_item_exist("chats", chatid):
                    # Chat doesn't exist
                    return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error
                    return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
            if not (client in chatdata["members"]):
                # User not in chat
                return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)

        # Create post format
        post_w_metadata = {}
        post_w_metadata["state"] = state
        post_w_metadata["u"] = str(client)
        post_w_metadata["chatid"] = str(chatid)
        
        self.log("{0} modifying {1} state to {2}".format(client, chatid, state))

        if chatid == "livechat":
            self.sendPacket({"cmd": "direct", "val": post_w_metadata})
        else:
            for member in chatdata["members"]:
                self.sendPacket({"cmd": "direct", "val": post_w_metadata, "id": member})
        
        # Tell client message was sent
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        
        # Rate limit user
        self.supporter.ratelimit(client)
    
    def post_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if (type(val) == dict) and (("p" in val) and (type(val["p"]) == str)) and (("chatid" in val) and (type(val["chatid"]) == str)):
                post = val["p"]
                chatid = val["chatid"]
                if (not len(post) > 360) and (not len(chatid) > 50):
                    if not self.supporter.check_for_spam("posts", client, burst=6, seconds=5):
                        if chatid == "livechat":
                            result = self.createPost(post_origin=chatid, user=client, content=post)
                            if result:
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                self.supporter.ratelimit(client)
                            else:
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            result, chat_data = self.filesystem.load_item("chats", chatid)
                            if result:
                                if client in chat_data["members"]:
                                    result = self.createPost(post_origin=chatid, user=client, content=post)
                                    if result:
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                        self.supporter.ratelimit(client)
                                    else:
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Rate limiter
                        self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Message too large
                    self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def add_to_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if (("username" in val) and (type(val["username"]) == str)) and (("chatid" in val) and (type(val["chatid"]) == str)):
                    username = val["username"]
                    chatid = val["chatid"]
                    
                    # Read chat UUID's nickname
                    FileRead, chatdata = self.filesystem.load_item("chats", chatid)
                    print(chatid)
                    if FileRead:
                        if client in chatdata["members"]:
                            # Add user to group chat
                            if (username not in chatdata["members"]) and (username != "Server"):
                                chatdata["members"].append(username)
                                FileWrite = self.filesystem.write_item("chats", chatid, chatdata)

                                if FileWrite:
                                    # Inbox message to say the user was added to the group chat
                                    self.createPost("inbox", username, "You have been added to the group chat '{0}' by @{1}!".format(chatdata["nickname"], client))

                                    # Tell client user was added
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Some other error, raise an internal error.
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "IDExists", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Some other error, raise an internal error.
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Bad syntax
                    self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def remove_from_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if (("username" in val) and (type(val["username"]) == str)) and (("chatid" in val) and (type(val["chatid"]) == str)):
                    username = val["username"]
                    chatid = val["chatid"]
                    
                    # Read chat UUID's nickname
                    result, chatdata = self.filesystem.load_item("chats", chatid)
                    if result:
                        if client == chatdata["owner"]:
                            if (client != username) and (username != "Server"):
                                # Remove user from group chat
                                chatdata["members"].remove(username)
                                result = self.filesystem.write_item("chats", chatid, chatdata)

                                if result:
                                    # Inbox message to say the user was removed from the group chat
                                    self.createPost("inbox", username, "You have been removed from the group chat '{0}' by @{1}!".format(chatdata["nickname"], client))

                                    # Tell client user was added
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Some other error, raise an internal error.
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Some other error, raise an internal error.
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Bad syntax
                    self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def get_inbox(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if ("page" in val) and self.checkForInt(val["page"]):
                    page = int(val["page"])
                else:
                    page = 1
                
                inbox_index = self.getIndex(location="posts", query={"post_origin": "inbox", "u": {"$in": [client, "Server"]}, "isDeleted": False}, page=page)
                for i in range(len(inbox_index["index"])):
                    inbox_index["index"][i] = inbox_index["index"][i]["_id"]
                inbox_index["index"].reverse()
                payload = {
                    "mode": "inbox",
                    "payload": inbox_index
                }
                self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

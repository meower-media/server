from copy import copy
import time

from src.util import status
from src.entities import users, accounts, networks, sessions, infractions, posts, chats, messages, notifications
from src.database import db
from src.util import sucurity

LEGACY_DEVICE = {
    "user_agent": "Unknown",
    "client_name": "Legacy Client",
    "client_version": "Unknown",
    "client_type": "Unknown"
}

class CL3Commands:
    def __init__(self, cl_server):
        self.cl = cl_server
    
    # Networking/client utilities
    
    async def ping(self, client, val, listener):
        # Check whether CL3 has been discontinued
        if time.time() > 1688169599:
            for client in copy(self.cl.clients):
                try:
                    await self.cl.kick_client(client)
                except:
                    pass
        else:
            await self.cl.send_code(client, "OK", listener)
    
    async def version_chk(self, client, val, listener):
        await self.cl.send_code(client, "OK", listener)
    
    async def get_ulist(self, client, val, listener):
        ulist = ""
        if hasattr( client, username):
            ulist = f"{client.username};"
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
        
        # Attempt to get session by token
        try:
            session = sessions.get_session_by_token(password, legacy=True)
        except:
            session = None
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
        if session:
            token = session.refresh(LEGACY_DEVICE, "127.0.0.1")
        else:
            token, session = sessions.create_user_session(account, LEGACY_DEVICE, "127.0.0.1", legacy=True)
        if user.id in self.cl._user_ids:
            await self.cl.kick_client(self.cl._user_ids[user.id], "IDConflict")
        client.session_id = session.id
        client.user_id = user.id
        client.username = username
        self.cl._user_ids[user.id] = client
        self.cl._usernames[username] = client
        for chat_id in (["livechat"] + chats.get_all_chat_ids(user.id)):
            if chat_id not in self.cl._chats:
                self.cl._chats[chat_id] = set()
            self.cl._chats[chat_id].add(client)
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "auth",
                "payload": {
                    "username": username,
                    "token": token
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
    
    """ pain.
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
    """
    
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
        home_index = [post.id for post in posts.get_latest_posts(skip=((page-1)*25))]

        # Return home index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "home",
                "payload": {
                    "index": home_index,
                    "page#": page,
                    "pages": ((db.posts.count_documents({"deleted_at": None}) // 25)+1),
                    "query": {
                        "post_origin": "home",
                        "isDeleted": False
                    }
                }
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
    
    """ not implemented
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
    """

    async def search_user_posts(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Get user ID
        if isinstance(val, dict) and ("query" in val) and isinstance(val["query"], str):
            try:
                user_id = users.get_id_from_username(val["query"])
            except status.resourceNotFound:
                return await self.cl.send_code(client, "IDNotFound", listener)
        else:
            return await self.cl.send_code(client, "Datatype", listener)

        # Get page
        if isinstance(val, dict) and ("page" in val) and isinstance(val["page"], int):
            page = val["page"]
        else:
            page = 1

        # Get index
        index = [post.id for post in posts.get_user_posts(user_id, skip=((page-1)*25))]

        # Return index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "user_posts",
                "index": {
                    "index": index,
                    "page#": page,
                    "pages": ((db.posts.count_documents({"deleted_at": None, "author_id": user_id}) // 25)+1),
                    "query": {
                        "post_origin": "home",
                        "u": val["query"],
                        "isDeleted": False
                    }
                }
            }
        }
        await self.cl.send_code(client, "OK", listener)
        return await self.cl.send_to_client(client, payload, listener)
    
    # Moderator features
    
    """
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
    """
            
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
    
    async def create_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, str):
            return await self.cl.send_code(client, "Datatype", listener)

        # Check length
        if len(val) < 1:
            return await self.cl.send_code(client, "Syntax", listener)
        elif len(val) > 20:
            return await self.cl.send_code(client, "TooLarge", listener)

        # Create chat
        chats.create_chat(val, client.user_id)

        # Tell the client the chat was created
        return await self.cl.send_code(client, "OK", listener)
    
    async def leave_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, str):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get chat
        try:
            chat = chats.get_chat(val)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)
        
        user = users.get_user(client.user_id)

        # Check if the client is in the chat
        if not chat.has_member(user):
            return await self.cl.send_code(client, "MissingPermissions", listener)
        
        # Check if the chat is a DM
        if chat.direct:
            return await self.cl.send_code(client, "MissingPermissions", listener)

        # Remove member from the chat
        chat.remove_member(user)

        # Tell the client the chat was deleted
        return await self.cl.send_code(client, "OK", listener)
    
    async def get_chat_list(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Get page
        if isinstance(val, dict) and ("page" in val) and isinstance(val["page"], int):
            page = val["page"]
            if page < 1:
                page = 1
        else:
            page = 1

        # Get chats
        chats_index = chats.get_all_chats(client.user_id, skip=((page-1)*25))

        # Return chats index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "chats",
                "payload": {
                    "index": [chat.id for chat in chats_index],
                    "all_chats": [chat.legacy_public for chat in chats_index],
                    "page#": page,
                    "pages": ((db.chats.count_documents({"members": {"$all": [client.user_id]}, "deleted_at": None}) // 25)+1),
                    "query": {
                        "members": {
                            "$all": [client.username]
                        }
                    }
                }
            }
        }
        await self.cl.send_code(client, "OK", listener)
        return await self.cl.send_to_client(client, payload, listener)
    
    async def get_chat_data(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, str):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get chat
        try:
            chat = chats.get_chat(val)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)
        
        user = users.get_user(client.user_id)

        # Check if the client is in the chat
        if not chat.has_member(user):
            return await self.cl.send_code(client, "MissingPermissions", listener)

        # Return chat data
        chat_json = chat.legacy_public
        chat_json["chatid"] = chat_json["_id"]
        del chat_json["_id"]
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "chat_data",
                "payload": chat_json
            }
        }
        await self.cl.send_code(client, "OK", listener)
        return await self.cl.send_to_client(client, payload, listener)
    
    async def get_chat_posts(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)

        # Check datatype
        if not isinstance(val, str):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get chat
        try:
            chat = chats.get_chat(val)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)

        user = users.get_user(client.user_id)

        # Check if the client is in the chat
        if not chat.has_member(user):
            return await self.cl.send_code(client, "MissingPermissions", listener)

        # Get messages index
        messages_index = [message.id for message in messages.get_latest_messages(chat, limit=25)]

        # Return messages index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "chat_posts",
                "payload": {
                    "index": messages_index,
                    "page#": 1,
                    "pages": ((db.posts.count_documents({"chat_id": chat.id, "deleted_at": None}) // 25)+1),
                    "query": {
                        "post_origin": chat.id,
                        "isDeleted": False
                    }
                }
            }
        }
        await self.cl.send_code(client, "OK", listener)
        return await self.cl.send_to_client(client, payload, listener)

    async def set_chat_state(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, dict):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get chat ID
        if ("chatid" in val) and isinstance(val["chatid"], str):
            chat_id = val["chatid"]
        else:
            return await self.cl.send_code(client, "Datatype", listener)

        # Get state
        if ("state" in val) and isinstance(val["state"], int):
            state = val["state"]
        else:
            return await self.cl.send_code(client, "Datatype", listener)

        try:
            chat = chats.get_chat(chat_id)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)

        user = users.get_user(client.user_id)

        # Check if the client is in the chat
        if not chat.has_member(user):
            return await self.cl.send_code(client, "MissingPermissions", listener)
        
        # Broadcast new chat state
        if state == 100:
            chat.emit_typing(user)
            return await self.cl.send_code(client, "OK", listener)
        else:
            payload = {
                "cmd": "direct",
                "val": {
                    "chatid": chat_id,
                    "u": client.username,
                    "state": state
                }
            }
            await self.cl.send_code(client, "OK", listener)
            return await self.cl.send_to_chat(chat_id, payload)
    
    async def post_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, dict):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get chat ID
        if ("chatid" in val) and isinstance(val["chatid"], str):
            chat_id = val["chatid"]
        else:
            return await self.cl.send_code(client, "Datatype", listener)

        # Get content
        if ("p" in val) and isinstance(val["p"], str):
            content = val["p"]
        else:
            return await self.cl.send_code(client, "Datatype", listener)

        # Check length
        if len(content) > 360:
            return await self.cl.send_code(client, "TooLarge", listener)
        
        # Get user
        user = users.get_user(client.user_id, return_deleted=False)

        # Get chat
        try:
            chat = chats.get_chat(chat_id)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)

        # Check if the client is in the chat
        if not chat.has_member(user):
            return await self.cl.send_code(client, "IDNotFound", listener)

        # Check whether the user is suspended
        moderation_status = infractions.user_status(user)
        if moderation_status["suspended"] or moderation_status["banned"]:
            return await self.cl.send_code(client, "Banned", listener)

        # Create message
        messages.create_message(chat, user, content)

        # Tell the client the message was created
        return await self.cl.send_code(client, "OK", listener)
    
    async def add_to_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, dict):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get chat ID
        if ("chatid" in val) and isinstance(val["chatid"], str):
            chat_id = val["chatid"]
        else:
            return await self.cl.send_code(client, "Datatype", listener)

        # Get username
        if ("username" in val) and isinstance(val["username"], str):
            username = val["username"]
        else:
            return await self.cl.send_code(client, "Datatype", listener)
        
        # Get user
        user = users.get_user(client.user_id, return_deleted=False)

        # Get chat
        try:
            chat = chats.get_chat(chat_id)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)

        # Check if the client is in the chat
        if not chat.has_member(user):
            return await self.cl.send_code(client, "MissingPermissions", listener)

        # Check whether the user is suspended
        moderation_status = infractions.user_status(user)
        if moderation_status["suspended"] or moderation_status["banned"]:
            return await self.cl.send_code(client, "Banned", listener)

        # Add member to chat
        chat.add_member(users.get_user(users.get_id_from_username(username)))

        # Tell the client the member was added
        return await self.cl.send_code(client, "OK", listener)

    async def remove_from_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Check datatype
        if not isinstance(val, dict):
            return await self.cl.send_code(client, "Datatype", listener)

        # Get chat ID
        if ("chatid" in val) and isinstance(val["chatid"], str):
            chat_id = val["chatid"]
        else:
            return await self.cl.send_code(client, "Datatype", listener)

        # Get username
        if ("username" in val) and isinstance(val["username"], str):
            username = val["username"]
        else:
            return await self.cl.send_code(client, "Datatype", listener)
        
        # Get user
        user = users.get_user(client.user_id, return_deleted=False)

        # Get chat
        try:
            chat = chats.get_chat(chat_id)
        except status.resourceNotFound:
            return await self.cl.send_code(client, "IDNotFound", listener)

        # Check if the client is in the chat and has permission
        if (not chat.has_member(user)) or (chat.permissions.get(user.id, 0) < 1):
            return await self.cl.send_code(client, "MissingPermissions", listener)

        # Remove member from chat
        chat.remove_member(users.get_user(users.get_id_from_username(username)))

        # Tell the client the member was removed
        return await self.cl.send_code(client, "OK", listener)

    async def get_inbox(self, client, val, listener):
        # Check if the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "Refused", listener)
        
        # Get page
        if isinstance(val, dict) and ("page" in val) and isinstance(val["page"], int):
            page = val["page"]
            if page < 1:
                page = 1
        else:
            page = 1

        # Get inbox index
        inbox_index = [notification.id for notification in notifications.get_user_notifications(client.user_id, skip=((page-1)*25))]

        # Return inbox index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "inbox",
                "payload": {
                    "index": inbox_index,
                    "page#": page,
                    "pages": ((db.notifications.count_documents({"recipient_id": client.user_id}) // 25)+1),
                    "query": {
                        "post_origin": "inbox",
                        "u": {
                            "$in": [client.username, "Server"]
                        },
                        "isDeleted": False
                    }
                }
            }
        }
        await self.cl.send_code(client, "OK", listener)
        return await self.cl.send_to_client(client, payload, listener)

import secrets
import copy

class Meower:

    """
    Meower
    
    This class is a CL4-compatible collection of commands.
    All commands here are optimized for performance and readability.
    
    Meower inherits cloudlink from the built-in cloudlink command
    loader and inherits main, providing access to the database
    and security interfaces.
    
    """
    
    def __init__(self, cloudlink, parent):
        # Inherit cloudlink when initialized by cloudlink's custom command loader
        self.cloudlink = cloudlink
        
        # Inherit parent class attributes
        self.parent = parent
        self.supporter = parent.supporter
        self.db = parent.db
        self.accounts = parent.accounts
        self.log = parent.log
        self.importer_ignore_functions = ["getIndex", "createPost"]
        
        self.log("Meower CL4 commands initialized!")
    
    # Extra functionality that is required for Meower to work.
    def getIndex(self, location="posts", query={"post_origin": "home", "isDeleted": False}, truncate=False, page=1, sort="t.e"):
        if truncate:
            all_items = self.db.dbclient[location].find(query).sort("t.e", self.db.pymongo.DESCENDING).skip((page-1)*25).limit(25)
        else:
            all_items = self.db.dbclient[location].find(query)
        
        item_count = self.db.dbclient[location].count_documents(query)
        if item_count == 0:
            pages = 0
        else:
            if (item_count % 25) == 0:
                if (item_count < 25):
                    pages = 1
                else:
                    pages = (item_count // 25)
            else:
                pages = (item_count // 25)+1

        query_get = []
        for item in all_items:
            query_get.append(item)
        
        query_return = {
            "query": query,
            "index": query_get,
            "page#": page,
            "pages": pages
        }
        
        return query_return
    
    async def createPost(self, post_origin, user, content):
        post_id = str(self.parent.uuid.uuid4())
        timestamp = self.supporter.timestamp(1).copy()
        content = self.supporter.wordfilter(content)
        if post_origin == "home":
            post_data = {
                "type": 1,
                "post_origin": str(post_origin), 
                "u": str(user), 
                "t": timestamp, 
                "p": str(content), 
                "post_id": post_id, 
                "isDeleted": False
            }

            result = self.db.create_item("posts", post_id, post_data)

            if result:
                payload = post_data
                payload["mode"] = 1

                await self.cloudlink.sendPacket(
                    copy.copy(self.cloudlink.all_clients),
                    {
                        "cmd": "direct",
                        "val": payload
                    }, 
                    ignore_rooms = True)
                return True
            else:
                return False
        
        elif post_origin == "inbox":
            post_data = {
                "type": 2,
                "post_origin": str(post_origin), 
                "u": str(user), 
                "t": timestamp, 
                "p": str(content), 
                "post_id": post_id, 
                "isDeleted": False
            }

            result = self.db.create_item("posts", post_id, post_data)

            if result:
                payload = {
                    "mode": "inbox_message",
                    "payload": {}
                }
                if user == "Server":
                    self.db.dbclient["usersv0"].update_many({"unread_inbox": False}, {"$set": {"unread_inbox": True}})
                    
                    await self.cloudlink.sendPacket(
                        copy.copy(self.cloudlink.all_clients),
                        {
                            "cmd": "direct",
                            "val": payload
                        }, 
                        ignore_rooms = True)
                
                elif user in self.user_sessions:
                    self.db.dbclient["usersv0"].update_many({"_id": user, "unread_inbox": False}, {"$set": {"unread_inbox": True}})
                    
                    tmp_list = self.cloudlink.selectMultiUserObjects(list(self.parent.user_sessions[user]), rooms = self.cloudlink.getAllRooms(), force = True)
        
                    # Make the user object list iterable if it's not
                    if not type(tmp_list) == list:
                        tmp_list = [tmp_list]
                    
                    for client in tmp_list:
                        await self.cloudlink.sendPacket(
                            client,
                            {
                                "cmd": "direct",
                                "val": payload
                            }, 
                            ignore_rooms = True)
                return True
            else:
                return False
        
        elif post_origin == "livechat":
            post_data = {
                "type": 1,
                "post_origin": str(post_origin), 
                "u": str(user), 
                "t": timestamp, 
                "p": str(content), 
                "post_id": post_id, 
                "isDeleted": False
            }

            payload = post_data
            payload["state"] = 2

            # Broadcast the updated user's chat state
            await self.cloudlink.sendPacket(
                self.cloudlink.getAllUsersInRoom("livechat"),
                {
                    "cmd": "direct",
                    "val": payload
                },
                ignore_rooms = True
            )
            
            return True
        else:
            result, chat_data = self.db.load_item("chats", post_origin)
            if result:
                post_data = {
                    "type": 1,
                    "post_origin": str(post_origin), 
                    "u": str(user), 
                    "t": timestamp, 
                    "p": str(content), 
                    "post_id": post_id, 
                    "isDeleted": False
                }

                result = self.db.create_item("posts", post_id, post_data)

                if result:
                    # Remove code below once client is updated
                    payload = post_data
                    payload["state"] = 2

                    # Broadcast the user's chat message
                    await self.cloudlink.sendPacket(
                        self.cloudlink.getAllUsersInRoom(post_origin),
                        {
                            "cmd": "direct",
                            "val": payload
                        },
                        ignore_rooms = True
                    )
                    return True
                else:
                    return False
            else:
                return False
    
    # Command overrides - These commands will override built-in commands (requires disabling built-in commands before custom commands are loaded)
    
    async def link(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(
                client,
                "IDRequired",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # TODO: check if the room being linked to is a chat, and prevent user from linking if they do not have permissions
        
        # Passthrough commands, reference server's internal command handlers because referencing the command directly causes a recursion loop
        # self.link becomes an alias of self.cloudlink.link
        await self.cloudlink.serverInternalHandlers.link(client, message, listener_detected, listener_id, room_id)
    
    async def unlink(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(
                client,
                "IDRequired",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Passthrough commands, reference server's internal command handlers because referencing the command directly causes a recursion loop
        # self.unlink becomes an alias of self.cloudlink.unlink
        await self.cloudlink.serverInternalHandlers.unlink(client, message, listener_detected, listener_id, room_id)
    
    # Meower accounts and security
    
    async def deauth(self, client, message, listener_detected, listener_id, room_id):
        # Check if already authenticated
        if not client.authed:
            await self.cloudlink.sendCode(
                client,
                "IDRequired",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Read account data
        user_data = self.accounts.get_account(client.friendly_username, False, False)
        match user_data:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountDoesNotExist:
                await self.cloudlink.sendCode(
                    client,
                    "IDNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        self.log(f"{client.id} Logging out...")
        
        username = client.friendly_username
        
        # Remove user attributes
        client.authed = False
        client.friendly_username = None
        
        # Session management
        if client.session_token in user_data["tokens"]:
            user_data["tokens"].remove(client.session_token)
        
        if client.id in self.parent.user_sessions[username]:
            self.parent.user_sessions[username].remove(client.id)
        online = (len(self.parent.user_sessions[username]) != 0)
        
        # Update the account state
        args = {
            "last_ip": client.full_ip,
            "online": online
        }
        
        # Revoke all inactive sessions by removing all tokens
        if not online:
            args["tokens"] = []
        
        self.accounts.update_setting(
            username,
            args,
            forceUpdate = True
        )
        
        # Tell all clients that someone is no longer online
        if not online:
            for client_tmp in copy.copy(self.cloudlink.all_clients):
                if not client_tmp == client:
                    await self.cloudlink.sendPacket(
                        client_tmp,
                        {
                            "cmd": "direct",
                            "val": {
                                "mode": "offline",
                                "username": username
                            }
                        }, 
                        ignore_rooms = True)
        
        # Tell the client they were logged out successfully
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id
        )
    
    async def auth_pswd(self, client, message, listener_detected, listener_id, room_id):
        # Check if already authenticated
        if client.authed:
            await self.cloudlink.sendCode(
                client,
                "IDSet",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if val key contains the correct dictionary keys
        for entry in ["username", "pswd"]:
            if not entry in message["val"]:
                await self.cloudlink.sendCode(
                    client,
                    "Syntax",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Read keys
        username = message["val"]["username"]
        pswd =  message["val"]["pswd"]
        
        # Check if key datatypes are correct
        if not((type(username) == str) and (type(pswd) == str)):
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if there are unsupported characters in the keys
        if self.supporter.checkForBadCharsUsername(username) or self.supporter.checkForBadCharsPost(pswd):
            await self.cloudlink.sendCode(
                client,
                "IllegalChars",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("login", client, burst=5, seconds=60):
            await self.cloudlink.sendCode(
                client,
                "RateLimit",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Anti ban login
        result = self.accounts.is_account_banned(username)
        match result:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountBanned:
                await self.cloudlink.sendCode(
                    client,
                    "Banned",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return

            case self.accounts.accountDoesNotExist:
                await self.cloudlink.sendCode(
                    client,
                    "IDNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        is_token = False
        # Authenticate
        result = self.accounts.authenticate(username, pswd)
        match result:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountNotAuthenticated:
                await self.cloudlink.sendCode(
                    client,
                    "PasswordInvalid",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountAuthenticatedWithToken:
                is_token = True
        
        # Create / load the netlog
        self.db.create_item("netlog", client.full_ip, {"users": [], "last_user": username})
        status, netlog = self.db.load_item("netlog", client.full_ip)
        if not status:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Update the netlog
        if not username in netlog["users"]:
            netlog["users"].append(username)
        netlog["last_user"] = username
        self.db.write_item("netlog", client.full_ip, netlog)
        
        # Read account data
        user_data = self.accounts.get_account(username, False, False)
        match user_data:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountDoesNotExist:
                await self.cloudlink.sendCode(
                    client,
                    "IDNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Session management
        
        if is_token:
            # If the token is valid, replace the token with a new one
            user_data["tokens"].remove(pswd)
        
        token = secrets.token_urlsafe(64)
        user_data["tokens"].append(token)
        
        if not username in self.parent.user_sessions:
            self.parent.user_sessions[username] = set()
        if not client.id in self.parent.user_sessions[username]:
            self.parent.user_sessions[username].add(client.id)
        
        # Update the account state
        self.accounts.update_setting(
            username,
            {
                "last_ip": client.full_ip,
                "online": True,
                "tokens": user_data["tokens"]
            }, 
            forceUpdate = True
        )
        
        # AutoID the client
        # Tell the client it was successfully authenticated
        extra_data = {
            "token": token
        }
        
        client.authed = True
        client.session_token = token
        
        await self.supporter.autoID(
            client,
            username,
            echo = True,
            listener_detected = listener_detected,
            listener_id = listener_id,
            extra_data = extra_data
        )
        
        # Alert all clients that an account is online
        if len(self.parent.user_sessions[username]) == 1:
            for client_tmp in copy.copy(self.cloudlink.all_clients):
                if not client_tmp == client:
                    await self.cloudlink.sendPacket(
                        client_tmp,
                        {
                            "cmd": "direct",
                            "val": {
                                "mode": "online",
                                "username": username
                            }
                        },
                        ignore_rooms = True)
    
    async def gen_account(self, client, message, listener_detected, listener_id, room_id):
        # Check if already authenticated
        if client.authed:
            await self.cloudlink.sendCode(
                client,
                "IDSet",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if val key contains the correct dictionary keys
        for entry in ["username", "pswd"]:
            if not entry in message["val"]:
                await self.cloudlink.sendCode(
                    client,
                    "Syntax",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Read keys
        username = message["val"]["username"]
        pswd =  message["val"]["pswd"]
        
        # Check if key datatypes are correct
        if not((type(username) == str) and (type(pswd) == str)):
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if there are unsupported characters in the keys
        if self.supporter.checkForBadCharsUsername(username) or self.supporter.checkForBadCharsPost(pswd):
            await self.cloudlink.sendCode(
                client,
                "IllegalChars",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("login", client, burst=5, seconds=60):
            await self.cloudlink.sendCode(
                client,
                "RateLimit",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Create account
        result = self.accounts.create_account(username, pswd)
        match result:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountExists:
                await self.cloudlink.sendCode(
                    client,
                    "IDExists",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Read account data
        user_data = self.accounts.get_account(username, False, False)
        if user_data == self.accounts.accountIOError:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Create / load the netlog
        self.db.create_item("netlog", client.full_ip, {"users": [], "last_user": username})
        status, netlog = self.db.load_item("netlog", client.full_ip)
        if not status:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Update the netlog
        if not username in netlog["users"]:
            netlog["users"].append(username)
        netlog["last_user"] = username
        self.db.write_item("netlog", client.full_ip, netlog)
        
        # Session management
        token = secrets.token_urlsafe(64)
        if not username in self.parent.user_sessions:
            self.parent.user_sessions[username] = set()
        if not client.id in self.parent.user_sessions[username]:
            self.parent.user_sessions[username].add(client.id)
        
        # Update the account state
        self.accounts.update_setting(
            username,
            {
                "last_ip": client.full_ip,
                "online": True,
                "tokens": [token]
            }, 
            forceUpdate = True
        )
        
        # AutoID the client
        # Tell the client it was successfully authenticated
        extra_data = {
            "tokens": token
        }
        
        # TODO: Send welcome message to client
        
        client.authed = True
        client.session_token = token
        
        await self.supporter.autoID(
            client,
            username,
            echo = True,
            listener_detected = listener_detected,
            listener_id = listener_id,
            extra_data = extra_data
        )
        
        # Alert all clients that an account is online
        for client in copy.copy(self.cloudlink.all_clients):
            await self.cloudlink.sendPacket(
                client,
                {
                    "cmd": "direct",
                    "val": {
                        "mode": "online",
                        "username": username
                    }
                }, 
                ignore_rooms = True)
    
    async def get_profile(self, client, message, listener_detected, listener_id, room_id):
        # Removing authentication check because all clients should be able to get the homepage regardless of login state
        
        # Check datatype
        if not type(message["val"]) == str:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Get the user's data, This should remove sensitive data in general
        omitSensitive = client.friendly_username != message["val"]
        isClient = client.friendly_username == message["val"]
        result = self.accounts.get_account(message["val"], omitSensitive, isClient)
        match result:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountDoesNotExist:
                await self.cloudlink.sendCode(
                    client,
                    "IDNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        result["is_self"] = (client.friendly_username == message["val"])
        
        # Report client data
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id,
            extra_data = result
        )
    
    async def update_config(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(
                client,
                "IDRequired",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("update-config", client, burst=1, seconds=1):
            await self.cloudlink.sendCode(
                client,
                "RateLimit",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Update the user's data
        result = self.accounts.update_setting(client.friendly_username, message["val"])
        match result:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountBanned:
                await self.cloudlink.sendCode(
                    client,
                    "Banned",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountDoesNotExist:
                await self.cloudlink.sendCode(
                    client,
                    "IDNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Tell the client that their config was updated
        await self.cloudlink.sendCode(client, "OK", listener_detected, listener_id)
        
        # Alert all clients that their config was updated
        
        payload = dict()
        payload["mode"] = "config_update"
        payload["username"] = client.friendly_username
        payload.update(self.accounts.get_account(client.friendly_username, True, False))
        
        for client_tmp in copy.copy(self.cloudlink.all_clients):
            await self.cloudlink.sendPacket(
                client_tmp,
                {
                    "cmd": "direct",
                    "val": payload
                }, 
                ignore_rooms = True)
    
    async def change_pswd(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(
                client,
                "IDRequired",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if val key contains the correct dictionary keys
        for entry in ["old_pswd", "new_pswd"]:
            if not entry in message["val"]:
                await self.cloudlink.sendCode(
                    client,
                    "Syntax",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Read keys
        old_pswd = message["val"]["old_pswd"]
        new_pswd =  message["val"]["new_pswd"]
        
        # Check if key datatypes are correct
        if not((type(old_pswd) == str) and (type(new_pswd) == str)):
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if there are unsupported characters in the keys
        if self.supporter.checkForBadCharsPost(old_pswd) or self.supporter.checkForBadCharsPost(new_pswd):
            await self.cloudlink.sendCode(
                client,
                "IllegalChars",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("password-change", client, burst=5, seconds=60):
            await self.cloudlink.sendCode(
                client,
                "RateLimit",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Verify that the old password is correct
        result = self.accounts.authenticate(client.friendly_username, old_pswd)
        match result:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountBanned:
                await self.cloudlink.sendCode(
                    client,
                    "Banned",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountNotAuthenticated:
                await self.cloudlink.sendCode(
                    client,
                    "PasswordInvalid",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Update the user's password
        result = self.accounts.change_password(client.friendly_username, new_pswd)
        match result:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountBanned:
                await self.cloudlink.sendCode(
                    client,
                    "Banned",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountDoesNotExist:
                await self.cloudlink.sendCode(
                    client,
                    "IDNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Tell the client that the password was changed successfully
        await self.cloudlink.sendCode(
                client,
                "OK",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
    
    async def del_tokens(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(
                client,
                "IDRequired",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("token-clear", client, burst=5, seconds=60):
            await self.cloudlink.sendCode(
                client,
                "RateLimit",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        username = client.friendly_username
        
        # Update the user's data
        result = self.accounts.update_setting(
            username,
            {
                "last_ip": client.full_ip,
                "online": False,
                "tokens": []
            },
            forceUpdate = True
        )
        match result:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountBanned:
                await self.cloudlink.sendCode(
                    client,
                    "Banned",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountDoesNotExist:
                await self.cloudlink.sendCode(
                    client,
                    "IDNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        # Deauth all clients with the username
        tmp_list = self.cloudlink.selectMultiUserObjects(list(self.parent.user_sessions[username]), rooms = self.cloudlink.getAllRooms(), force = True)
        
        # Make the user object list iterable if it's not
        if not type(tmp_list) == list:
            tmp_list = [tmp_list]
        
        for client_tmp in tmp_list:
            if not client_tmp.id == client.id:
                client_tmp.authed = False
                client_tmp.friendly_username = None
                client_tmp.session_token = None
                
                # Alert the client that their session was revoked
                await self.cloudlink.sendPacket(
                    client_tmp,
                    {
                        "cmd": "direct",
                        "val": {
                            "mode": "session_revoked"
                        }
                    }, 
                    ignore_rooms = True)
        
        # Tell the client that all tokens were cleared
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id
        )
        
        # Tell all clients that someone is no longer online
        for client in copy.copy(self.cloudlink.all_clients):
            await self.cloudlink.sendPacket(
                client,
                {
                    "cmd": "direct",
                    "val": {
                        "mode": "offline",
                        "username": username
                    }
                }, 
                ignore_rooms = True)
    
    async def del_account(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(
                client,
                "IDRequired", 
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        result = self.accounts.get_account(client.friendly_username, False, True)
        match result:
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            case self.accounts.accountDoesNotExist:
                await self.cloudlink.sendCode(
                    client,
                    "IDNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Deauth all clients with the username
        tmp_list = self.cloudlink.selectMultiUserObjects(list(self.parent.user_sessions[client.friendly_username]), rooms = self.cloudlink.getAllRooms(), force = True)
        
        # Make the user object list iterable if it's not
        if not type(tmp_list) == list:
            tmp_list = [tmp_list]
        
        for client_tmp in tmp_list:
            if not client_tmp.id == client.id:
                client_tmp.authed = False
                client_tmp.friendly_username = None
                client_tmp.session_token = None
                await self.cloudlink.rejectClient(client_tmp, "Account deletion request")
        
        # Get all posts and delete them
        all_posts = self.db.get_index(
                location = "posts",
                query = {
                    "u": client.friendly_username
                }, 
                truncate=False
            )["index"]
        for post in all_posts:
            self.db.delete_item("posts", post["_id"])
            # complete report
            if post["post_origin"] != "inbox":
                pass # Broadcast an inbox delete message to client
        
        # Get all chats and delete them
        all_chats = self.db.get_index(
                location = "chats",
                query = {
                    "members": {
                        "$all": [client.friendly_username]
                        }
                }, 
                truncate=False
            )["index"]
        for chat in all_chats:
            if chat["owner"] == client.friendly_username:
                # Delete the chat
                self.db.delete_item("chats", chat["_id"])
                
                # Get all currently connected clients, check if they are in a chat, and then alert members that a client has left
                tmp_ulist = self.cloudlink.getAllUsersInManyRooms(self.cloudlink.getAllRooms())
                for member in chat["members"]:
                    if member in tmp_ulist:
                        pass # Alert user that a client was removed from their chat
            else:
                # Remove client from chat member list
                chat["members"].remove(client.friendly_username)
                self.db.write_item("chats", chat["_id"], chat)
        
        # Delete all netlog entries of the user
        netlog_index = self.db.get_index(
                location = "netlog",
                query = {
                    "users": {
                        "$all": [client.friendly_username]
                        }
                }, 
                truncate=False
            )["index"]
        for ip in netlog_index:
            ip["users"].remove(client.friendly_username)
            
            # Delete the IP address if no other clients exist on it
            if len(ip["users"]) == 0:
                self.db.delete_item("netlog", ip["_id"])
            # Remove user from last users list
            else:
                if ip["last_user"] == client:
                    ip["last_user"] = ip["users"][(len(ip["users"])-1)]
                self.db.write_item("netlog", ip["_id"], ip)
        
        # Delete the user datafile from the usersv0 database
        self.db.delete_item("usersv0", client.friendly_username)
        # TODO: Complete any reports present for that client
        
        client.friendly_username = ""
        client.username_set = False
        client.authed = False
        
        # Tell the client that the account was deleted
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id
        )
    
    # Meower general functionality
    
    async def post_home(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == str:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Message size check
        if len(message["val"]) > 360:
            await self.cloudlink.sendCode(
                client,
                "TooLarge",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("posts", client, burst=6, seconds=5):
            await self.cloudlink.sendCode(
                client,
                "RateLimit",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Create the post
        result = await self.createPost(post_origin = "home", user = client.friendly_username, content = message["val"])
        if result:
            await self.cloudlink.sendCode(client, "OK", listener_detected, listener_id)
        else:
            await self.cloudlink.sendCode(client, "InternalServerError", listener_detected, listener_id)
    
    # Meower logging and data management
    
    async def get_peak_users(self, client, message, listener_detected, listener_id, room_id):
        # Removing authentication check because all clients should be able to check the peak users counter
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected,
            listener_id,
            extra_data = self.supporter.peak_users_logger
        )
    
    # Meower chat-related functionality
    
    async def delete_post(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check if a post exists
        if not self.db.does_item_exist("posts", message["val"]):
            await self.cloudlink.sendCode(
                client,
                "IDNotFound",
                listener_detected,
                listener_id
            )
            return
        
        result, payload = self.db.load_item("posts", message["val"])
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected,
                listener_id
            )
            return
        
        # Check if the message is from the client
        client_check = True
        client_check = client_check and payload["post_origin"] != "inbox"
        client_check = client_check and (payload["u"] == client.friendly_username) or ((payload["u"] == "Discord") and payload["p"].startswith(f"{client.friendly_username}"))
        
        if client_check:
            self.log(f"{client.friendly_username} deleting post {message['val']}")
            
            payload["isDeleted"] = True
            result = self.db.write_item("posts", message["val"], payload)
            if not result:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected,
                    listener_id
                )
                return
            
            # Alert all clients that a post was deleted
            for client in copy.copy(self.cloudlink.all_clients):
                await self.cloudlink.sendPacket(
                    client,
                    {
                        "cmd": "direct",
                        "val": {
                            "mode": "delete",
                            "id": message["val"]
                        }
                    }, 
                    ignore_rooms = True)
            
            # Tell client the post was deleted
            await self.cloudlink.sendCode(
                client,
                "OK",
                listener_detected,
                listener_id
            )
            return
        
        # Check if a client is an admin
        account_data = self.accounts.get_account(client.friendly_username, True, True)
        match account_data:
            case self.accounts.accountDoesNotExist:
                await self.cloudlink.sendCode(
                    client,
                    "IDNotFound",
                    listener_detected,
                    listener_id
                )
                return
            
            case self.accounts.accountIOError:
                await self.cloudlink.sendCode(
                        client,
                        "InternalServerError",
                        listener_detected,
                        listener_id
                    )
                return
        
        # Permissions check
        if account_data["lvl"] < 1:
            await self.cloudlink.sendCode(
                    client,
                    "MissingPermissions",
                    listener_detected,
                    listener_id
                )
            return
        
        self.log(f"{client.friendly_username} deleting post {message['val']}")
        
        payload["isDeleted"] = True
        result = self.db.write_item("posts", message["val"], payload)
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected,
                listener_id
            )
            return
        
        # Alert all clients that a post was deleted
            for client in copy.copy(self.cloudlink.all_clients):
                await self.cloudlink.sendPacket(
                    client,
                    {
                        "cmd": "direct",
                        "val": {
                            "mode": "delete",
                            "id": val
                        }
                    },
                    ignore_rooms = True)
        
        # Make an moderator alert
        if payload["post_origin"] != "inbox":
            self.createPost(post_origin = "inbox", user = payload["u"], content = f"One of your posts were removed by a moderator because it violated the Meower terms of service! If you think this is a mistake, please report this message and we will look further into it. Post: \"{payload['p']}\"")
            
            # Give report feedback
            # TODO
        
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected,
            listener_id
        )
    
    async def create_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == str:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Message size check
        if len(message["val"]) > 20:
            await self.cloudlink.sendCode(
                client,
                "TooLarge",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("chats", client, burst=5, seconds=60):
            await self.cloudlink.sendCode(
                client,
                "RateLimit",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the chat doesn't already exist
        if self.db.does_item_exist("chats", message["val"]):
            await self.cloudlink.sendCode(
                client,
                "ChatExists",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        chat_id = str(self.parent.uuid.uuid4())
        
        # Create the chat
        result = self.db.create_item("chats", chat_id, {"nickname": message["val"], "owner": client.friendly_username, "members": [client.friendly_username]})
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        result = await self.createPost(post_origin = chat_id, user = "Server", content = f"{client.friendly_username} created the chat {message['val']}!")
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id
        )
    
    async def leave_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == str:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Message size check
        if len(message["val"]) > 50:
            await self.cloudlink.sendCode(
                client,
                "TooLarge",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("chats", client, burst=5, seconds=60):
            await self.cloudlink.sendCode(
                client,
                "RateLimit",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the chat does exist
        if not self.db.does_item_exist("chats", message["val"]):
            await self.cloudlink.sendCode(
                client,
                "ChatNotFound",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Load the chat
        result, chat_data = self.db.load_item("chats", message["val"])
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the client has access to the chat
        if not client.friendly_username in chat_data["members"]:
            await self.cloudlink.sendCode(
                client,
                "MissingPermissions",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the client is the chat owner
        if chat_data["owner"] == client.friendly_username:
            result = self.db.delete_item("chats", message["val"])
            if not result:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            for member in chat_data["members"]:
                if member in self.cloudlink.getAllUsersInManyRooms(self.cloudlink.getAllRooms()):
                    # Get the client object(s)
                    clients = self.cloudlink.getUserObject(member, force = True)
                    
                    for client in clients:
                        await self.cloudlink.sendPacket(
                            client,
                            {
                                "cmd": "direct",
                                "val": {
                                    "mode": "delete",
                                    "id": chat_data["_id"]
                                }
                            },
                            ignore_rooms = True
                        )
        
        # Remove the client from the chat
        else:
            chat_data["members"].remove(client.friendly_username)
            result = self.db.write_item("chats", message["val"], chat_data)
            if not result:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            result = await self.createPost(post_origin = message["val"], user = "Server", content = f"{client.friendly_username} left the chat.")
            if not result:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Tell the client that they were removed / chat was deleted
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id
        )
    
    async def get_chat_list(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Get user's chats
        chat_index = self.getIndex(
            location = "chats",
            query = {
                "members": {
                    "$all": [client.friendly_username]
                }
            }, 
            truncate = True,
            sort = "nickname"
        )
        
        # Prepare the chat index
        chat_index["all_chats"] = []
        for i in range(len(chat_index["index"])):
            chat_index["all_chats"].append(chat_index["index"][i])
            chat_index["index"][i] = chat_index["index"][i]["_id"]
        chat_index["index"].reverse()
        chat_index["all_chats"].reverse()
        
        # Return the chat list to the user
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id,
            extra_data = chat_index
        )
    
    async def get_chat_data(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == str:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Message size check
        if len(message["val"]) > 50:
            await self.cloudlink.sendCode(
                client,
                "TooLarge",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the chat does exist
        if not self.db.does_item_exist("chats", message["val"]):
            await self.cloudlink.sendCode(
                client,
                "ChatNotFound",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Load the chat
        result, payload = self.db.load_item("chats", message["val"])
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the client has access to the chat
        if not client.friendly_username in payload["members"]:
            await self.cloudlink.sendCode(
                client,
                "MissingPermissions",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        payload = {
            "chatid": chatdata["_id"],
            "nickname": chatdata["nickname"],
            "owner": chatdata["owner"],
            "members": chatdata["members"]
        }
        
        # Return the chat data to the user
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id,
            extra_data = payload,
            extra_root_data = {
                "mode": "chat_data"
            }
        )
    
    async def get_chat_posts(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == str:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Message size check
        if len(message["val"]) > 50:
            await self.cloudlink.sendCode(
                client,
                "TooLarge",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the chat does exist
        if not self.db.does_item_exist("chats", message["val"]):
            await self.cloudlink.sendCode(
                client,
                "ChatNotFound",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Load the chat
        result, payload = self.db.load_item("chats", message["val"])
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the client has access to the chat
        if not client.friendly_username in payload["members"]:
            await self.cloudlink.sendCode(
                client,
                "MissingPermissions",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        posts_index = self.getIndex(location="posts", query={"post_origin": message["val"], "isDeleted": False}, truncate=True)
        for i in range(len(posts_index["index"])):
            posts_index["index"][i] = posts_index["index"][i]["_id"]
        
        # Return the chat post(s) to the user
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id,
            extra_data = posts_index
        )
    
    async def set_chat_state(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check for arguments
        for arg in ["state", "chatid"]:
            if not arg in message["val"]:
                await self.cloudlink.sendCode(
                    client,
                    "Syntax",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Check argument datatypes
        if (not type(message["val"]["chatid"]) == str) or (not type(message["val"]["state"]) == int):
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Message size check
        if len(message["val"]["chatid"]) > 50:
            await self.cloudlink.sendCode(
                client,
                "TooLarge",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
        
        # Extract arguments
        state = message["val"]["state"]
        chatid = message["val"]["chatid"]
        
        chat_data = None
        
        # Check for permissions
        if not chatid == "livechat":
            # Check if the chat does exist
            if not self.db.does_item_exist("chats", chatid):
                await self.cloudlink.sendCode(
                    client,
                    "ChatNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            result, payload = self.db.load_item("chats", chatid)
            if not result:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            # Check if the client has access to the chat
            if not client.friendly_username in payload["members"]:
                await self.cloudlink.sendCode(
                    client,
                    "MissingPermissions",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            chat_data = payload
        
        # Modify status of client's link state
        match state:
            case 0:
                self.log(f"{client.friendly_username} left {chatid}")
                self.cloudlink.unlinkClientFromRooms(client)
                client.linked_chat = None
            case 1:
                self.log(f"{client.friendly_username} joined {chatid}")
                self.cloudlink.linkClientToRooms(client, chatid)
                client.linked_chat = chatid
            case 2:
                self.log(f"{client.friendly_username} sending message in {chatid}")
            case _:
                self.log(f"{client.friendly_username} modifying {chatid} state to {state}")
        
        # Create message
        payload = dict()
        payload["mode"] = "set_state"
        payload["state"] = state
        payload["u"] = str(client.friendly_username)
        payload["chatid"] = str(chatid)
        
        # Broadcast the updated user's chat state
        await self.cloudlink.sendPacket(
            self.cloudlink.getAllUsersInRoom(chatid),
            {
                "cmd": "direct",
                "val": payload
            },
            ignore_rooms = True
        )
        
        # Tell the client that the chat state was updated
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id
        )
    
    async def post_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check for arguments
        for arg in ["p", "chatid"]:
            if not arg in message["val"]:
                await self.cloudlink.sendCode(
                    client,
                    "Syntax",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Check argument datatypes
        if (not type(message["val"]["p"]) == str) or (not type(message["val"]["chatid"]) == str):
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Message size check
        if (len(message["val"]["chatid"]) > 50) or (len(message["val"]["p"]) > 360):
            await self.cloudlink.sendCode(
                client,
                "TooLarge",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
        
        # Ratelimit
        if self.supporter.check_for_spam("posts", client, burst=6, seconds=5):
            await self.cloudlink.sendCode(
                client,
                "RateLimit",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Extract arguments
        post = message["val"]["p"]
        chatid = message["val"]["chatid"]
        
        # Send chat message
        if chatid == "livechat":
            result = await self.createPost(post_origin = chatid, user = client.friendly_username, content = post)
            if not result:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        else:
            # Check for permissions
            # Check if the chat does exist
            if not self.db.does_item_exist("chats", chatid):
                await self.cloudlink.sendCode(
                    client,
                    "ChatNotFound",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            result, chat_data = self.db.load_item("chats", chatid)
            if not result:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            # Check if the client has access to the chat
            if not client.friendly_username in chat_data["members"]:
                await self.cloudlink.sendCode(
                    client,
                    "MissingPermissions",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
            
            result = await self.createPost(post_origin = chatid, user = client.friendly_username, content = post)
            if not result:
                await self.cloudlink.sendCode(
                    client,
                    "InternalServerError",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Tell the client that the message was successfully created in chat
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id
        )
    
    async def add_to_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check for arguments
        for arg in ["username", "chatid"]:
            if not arg in message["val"]:
                await self.cloudlink.sendCode(
                    client,
                    "Syntax",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Check argument datatypes
        if (not type(message["val"]["username"]) == str) or (not type(message["val"]["chatid"]) == str):
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Message size check
        if (len(message["val"]["chatid"]) > 50) or (len(message["val"]["username"]) > 20):
            await self.cloudlink.sendCode(
                client,
                "TooLarge",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
        
        # Check if the chat does exist
        if not self.db.does_item_exist("chats", message["val"]["chatid"]):
            await self.cloudlink.sendCode(
                client,
                "ChatNotFound",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Load the chat
        result, chat_data = self.db.load_item("chats", message["val"]["chatid"])
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the client has access to the chat
        if not client.friendly_username in chat_data["members"]:
            await self.cloudlink.sendCode(
                client,
                "MissingPermissions",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the user isn't already part of the chat
        if message["val"]["username"] in chat_data["members"]:
            await self.cloudlink.sendCode(
                client,
                "MemberExists",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Add the user to the group chat
        chat_data["members"].append(message["val"]["username"])
        result = self.db.write_item("chats", message["val"]["chatid"], chat_data)
        
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Alert the user that they have been added to a chat
        result = await self.createPost("inbox", message["val"]["username"], "You have been added to the group chat '{0}'!".format(chat_data["nickname"]))
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        result = await self.createPost(post_origin = message["val"]["chatid"], user = "Server", content = f"{client.friendly_username} added {message['val']['username']} to the chat!")
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id
        )
    
    async def remove_from_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check for arguments
        for arg in ["username", "chatid"]:
            if not arg in message["val"]:
                await self.cloudlink.sendCode(
                    client,
                    "Syntax",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Check argument datatypes
        if (not type(message["val"]["username"]) == str) or (not type(message["val"]["chatid"]) == str):
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Message size check
        if (len(message["val"]["chatid"]) > 50) or (len(message["val"]["username"]) > 20):
            await self.cloudlink.sendCode(
                client,
                "TooLarge",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
        
        # Check if the chat does exist
        if not self.db.does_item_exist("chats", message["val"]["chatid"]):
            await self.cloudlink.sendCode(
                client,
                "ChatNotFound",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Load the chat
        result, chat_data = self.db.load_item("chats", message["val"]["chatid"])
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the client has access to the chat
        if not client.friendly_username in chat_data["members"]:
            await self.cloudlink.sendCode(
                client,
                "MissingPermissions",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check if the user is part of the chat
        if not message["val"]["username"] in chat_data["members"]:
            await self.cloudlink.sendCode(
                client,
                "MemberDoesNotExist",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Remove the user to the group chat
        chat_data["members"].remove(message["val"]["username"])
        result = self.db.write_item("chats", message["val"]["chatid"], chat_data)
        
        if not result:
            await self.cloudlink.sendCode(
                client,
                "InternalServerError",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Alert the user that they have been added to a chat
        await self.createPost("inbox", message["val"]["username"], "You have been removed from the group chat '{0}'.".format(chat_data["nickname"]))
        
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id
        )
    
    async def get_inbox(self, client, message, listener_detected, listener_id, room_id):
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Check for arguments
        for arg in ["page"]:
            if not arg in message["val"]:
                await self.cloudlink.sendCode(
                    client,
                    "Syntax",
                    listener_detected = listener_detected, 
                    listener_id = listener_id
                )
                return
        
        # Check argument datatypes
        if not type(message["val"]["page"]) == int:
            await self.cloudlink.sendCode(
                client,
                "DataType",
                listener_detected = listener_detected, 
                listener_id = listener_id
            )
            return
        
        # Get user's inbox
        inbox_index = self.getIndex(
            location = "posts",
            query = {
                "post_origin": "inbox",
                "u": {
                    "$in": [client, "Server"]
                },
                "isDeleted": False
            },
            page = page
        )
        
        # Prepare the index
        for i in range(len(inbox_index["index"])):
            inbox_index["index"][i] = inbox_index["index"][i]["_id"]
        inbox_index["index"].reverse()
        
        # Return the inbox index to the user
        await self.cloudlink.sendCode(
            client,
            "OK",
            listener_detected = listener_detected, 
            listener_id = listener_id,
            extra_data = inbox_index
        )
    
    # Meower moderator features
    
    async def report(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def close_report(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def clear_home(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def clear_user_posts(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def alert(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def announce(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def block(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def unblock(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def kick(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def get_user_ip(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def get_ip_data(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def get_user_data(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def ban(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def pardon(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def terminate(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def repair_mode(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
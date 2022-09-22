import secrets

class Meower:

    """
    Meower
    
    This class is a CL4-compatible collection of commands.
    All commands here retain full compatibility with the
    old CL3-based Meower server, but optimized for
    performance and readability.
    
    Meower inherits cloudlink from the built-in cloudlink command
    loader and inherits main, providing access to the database
    and security interfaces.
    
    CL4 will automatically convert old custom commands to new commands,
    so all commands here must retain the same command name as the CL3-based
    server.
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
        
        self.log("Meower cloudlink commands initialized!")
    
    async def __template__(self, client, message, listener_detected, listener_id, room_id):
        # This is a template for a custom command. This will be ignored by Cloudlink, since it is a private method.
        pass
    
    # Meower accounts and security
    
    async def authpswd(self, client, message, listener_detected, listener_id, room_id):
        # Check if already authenticated
        if client.authed:
            await self.cloudlink.sendCode(client, "IDSet", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(client, "DataType", listener_detected, listener_id)
            return
        
        # Check if val key contains the correct dictionary keys
        for entry in ["username", "pswd"]:
            if not entry in message["val"]:
                await self.cloudlink.sendCode(client, "Syntax", listener_detected, listener_id)
                return
        
        # Read keys
        username = message["val"]["username"]
        pswd =  message["val"]["pswd"]
        
        # Check if key datatypes are correct
        if not((type(username) == str) and (type(pswd) == str)):
            await self.cloudlink.sendCode(client, "DataType", listener_detected, listener_id)
            return
        
        # Check if there are unsupported characters in the keys
        if self.supporter.checkForBadCharsUsername(username) or self.supporter.checkForBadCharsPost(pswd):
            await self.cloudlink.sendCode(client, "IllegalChars", listener_detected, listener_id)
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("login", client, burst=5, seconds=60):
            await self.cloudlink.sendCode(client, "RateLimit", listener_detected, listener_id)
            return
        
        # Anti ban login
        result = self.accounts.is_account_banned(username)
        if result == self.accounts.accountReadError:
            await self.cloudlink.sendCode(client, "InternalServerError", listener_detected, listener_id)
            return
        if result == self.accounts.accountBanned:
            await self.cloudlink.sendCode(client, "Banned", listener_detected, listener_id)
            return
        if result == self.accounts.accountDoesNotExist:
            await self.cloudlink.sendCode(client, "IDNotFound", listener_detected, listener_id)
            return
        
        # Authenticate
        result = self.accounts.authenticate(username, pswd)
        if result in [self.accounts.accountReadError, self.accounts.accountWriteError]:
            await self.cloudlink.sendCode(client, "InternalServerError", listener_detected, listener_id)
            return
        if result == self.accounts.accountNotAuthenticated:
            await self.cloudlink.sendCode(client, "PasswordInvalid", listener_detected, listener_id)
            return
        
        # Create / load the netlog
        self.db.create_item("netlog", client.full_ip, {"users": [], "last_user": username})
        status, netlog = self.db.load_item("netlog", client.full_ip)
        if not status:
            await self.cloudlink.sendCode(client, "InternalServerError", listener_detected, listener_id)
            return
        
        # Update the netlog
        if not username in netlog["users"]:
            netlog["users"].append(username)
        netlog["last_user"] = username
        self.db.write_item("netlog", client.full_ip, netlog)
        
        # Read account data
        data = self.accounts.get_account(username, False, False)
        if data == self.accounts.accountReadError:
            await self.cloudlink.sendCode(client, "InternalServerError", listener_detected, listener_id)
            return
        if data == self.accounts.accountDoesNotExist:
            await self.cloudlink.sendCode(client, "IDNotFound", listener_detected, listener_id)
            return
        
        # Generate a session token
        token = secrets.token_urlsafe(64)
        data["tokens"].append(token)
        
        # Update the account state
        self.accounts.update_setting(username, {"last_ip": client.full_ip, "tokens": data["tokens"]}, forceUpdate = True)
        
        # AutoID the client
        # Tell the client it was successfully authenticated
        extra_data = {
            "token": token
        }
        client.authed = True
        await self.supporter.autoID(client, username, echo = True, listener_detected = listener_detected, listener_id = listener_id, extra_data = extra_data)
        
        pages, size, ulist = self.cloudlink.supporter.paginate_ulist(self.cloudlink.getUsernames("default"))
        await self.cloudlink.sendPacket(self.cloudlink.getAllUsersInRoom("default"), {"cmd": "ulist", "pages": pages, "size": size, "val": ulist}, ignore_rooms = True)
    
    async def gen_account(self, client, message, listener_detected, listener_id, room_id):
        # Check if already authenticated
        if client.authed:
            await self.cloudlink.sendCode(client, "IDSet", listener_detected, listener_id)
            return
        
        # Check datatype
        if not type(message["val"]) == dict:
            await self.cloudlink.sendCode(client, "DataType", listener_detected, listener_id)
            return
        
        # Check if val key contains the correct dictionary keys
        for entry in ["username", "pswd"]:
            if not entry in message["val"]:
                await self.cloudlink.sendCode(client, "Syntax", listener_detected, listener_id)
                return
        
        # Read keys
        username = message["val"]["username"]
        pswd =  message["val"]["pswd"]
        
        # Check if key datatypes are correct
        if not((type(username) == str) and (type(pswd) == str)):
            await self.cloudlink.sendCode(client, "DataType", listener_detected, listener_id)
            return
        
        # Check if there are unsupported characters in the keys
        if self.supporter.checkForBadCharsUsername(username) or self.supporter.checkForBadCharsPost(pswd):
            await self.cloudlink.sendCode(client, "IllegalChars", listener_detected, listener_id)
            return
        
        # Ratelimit
        if self.supporter.check_for_spam("login", client, burst=5, seconds=60):
            await self.cloudlink.sendCode(client, "RateLimit", listener_detected, listener_id)
            return
        
        # TODO: Verify that the client's IP is not a VPN/Proxy
        
        # Create account, and return the default data to be updated
        result, data = self.accounts.create_account(username, pswd)
        if result == self.accounts.accountWriteError:
            await self.cloudlink.sendCode(client, "InternalServerError", listener_detected, listener_id)
            return
        if result == self.accounts.accountExists:
            await self.cloudlink.sendCode(client, "IDExists", listener_detected, listener_id)
            return
        
        # Create / load the netlog
        self.db.create_item("netlog", client.full_ip, {"users": [], "last_user": username})
        status, netlog = self.db.load_item("netlog", client.full_ip)
        if not status:
            await self.cloudlink.sendCode(client, "InternalServerError", listener_detected, listener_id)
            return
        
        # Update the netlog
        if not username in netlog["users"]:
            netlog["users"].append(username)
        netlog["last_user"] = username
        self.db.write_item("netlog", client.full_ip, netlog)
        
        # Generate a session token
        token = secrets.token_urlsafe(64)
        data["tokens"].append(token)
        
        # Update the account state
        self.accounts.update_setting(username, {"last_ip": client.full_ip, "tokens": data["tokens"]}, forceUpdate = True)
        
        # AutoID the client
        # Tell the client it was successfully authenticated
        extra_data = {
            "token": token
        }
        client.authed = True
        
        # TODO: Send welcome message to client
        
        await self.supporter.autoID(client, username, echo = True, listener_detected = listener_detected, listener_id = listener_id, extra_data = extra_data)
        
        pages, size, ulist = self.cloudlink.supporter.paginate_ulist(self.cloudlink.getUsernames("default"))
        await self.cloudlink.sendPacket(self.cloudlink.getAllUsersInRoom("default"), {"cmd": "ulist", "pages": pages, "size": size, "val": ulist}, ignore_rooms = True)
    
    async def get_profile(self, client, message, listener_detected, listener_id, room_id):
        # Removing authentication check because all clients should be able to get the homepage regardless of login state
        # This should remove sensitive data, pass omitSensitive with True to self.accounts.get_account
        
        # TODO
        pass
    
    async def update_config(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def change_pswd(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def del_tokens(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def del_account(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    # Meower general functionality
    
    async def get_home(self, client, message, listener_detected, listener_id, room_id):
        # Removing authentication check because all clients should be able to get the homepage regardless of login state
        # TODO
        pass
    
    async def post_home(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def get_post(self, client, message, listener_detected, listener_id, room_id):
        # Removing authentication check because all clients should be able to get the homepage regardless of login state
        # However, this should check if you aren't authenticated if you are not reading homepage
        
        # TODO
        pass
    
    # Meower logging and data management
    
    async def get_peak_users(self, client, message, listener_detected, listener_id, room_id):
        # Removing authentication check because all clients should be able to check the peak users counter
        # TODO
        pass
    
    async def search_user_posts(self, client, message, listener_detected, listener_id, room_id):
        # Removing authentication check because all clients should be able to search for homepage content
        # However, this should check if you aren't authenticated if you are not reading homepage
        
        # TODO
        pass
    
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
    
    # Meower chat-related functionality
    
    async def delete_post(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def create_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def leave_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def get_chat_list(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def get_chat_data(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def get_chat_posts(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
        
    async def set_chat_state(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def post_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def add_to_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
        
    async def remove_from_chat(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
    async def get_inbox(self, client, message, listener_detected, listener_id, room_id):
        # Check if not authenticated
        if not client.authed:
            await self.cloudlink.sendCode(client, "IDRequired", listener_detected, listener_id)
            return
        
        # TODO
        pass
    
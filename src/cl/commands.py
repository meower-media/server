import requests
import os

class meower:
    def __init__(self, parent):
        self.parent = parent

        self.cached_safe_ips = set()

        # Reference parent objects - database and user account access
        self.db = parent.db
        self.accounts = parent.accounts

        # Reference peak users counter
        self.peak_users_logger = parent.supporter.peak_users_logger

        # Prepare shared usernames object
        # Dictionary storing user IDs with cloudlink.client objects in a set
        self.user_object_shared = dict() 

        # Get cloudlink object
        self.server = parent.server

        # Use CL4's formatted print logging
        self.log = parent.log

        # Misc functions
        self.supporter = self.server.supporter 

        # Access to all rooms / manage rooms
        self.rooms = self.server.rooms 

        # Access to all client objects as well as client management
        self.clients = self.server.clients 

        # Use for selecting rooms within messages
        self.get_rooms = self.supporter.get_rooms 

        # Various ways to send messages
        self.send_packet_unicast = self.server.send_packet_unicast
        self.send_packet_multicast = self.server.send_packet_multicast
        self.send_packet_multicast_variable = self.server.send_packet_multicast_variable
        self.send_code = self.server.send_code

        # Bind events
        self.server.bind_event(self.server.events.on_connect, self.on_connect)
        self.server.bind_event(self.server.events.on_close, self.on_close)

        # Mark events as ignored for importing
        self.importer_ignore_functions = ["on_connect", "on_close"]

        # Define required/optional arguments, valid argument datatypes, and permitted sizes
        self.validator = {
            "TEMPLATE": {
                "required": {
                    "val": self.supporter.keydefaults["val"],
                    "id": self.supporter.keydefaults["id"],
                    "listener": self.supporter.keydefaults["listener"],
                    "rooms": self.supporter.keydefaults["rooms"]
                },
                "optional": ["id", "listener", "rooms"],
                "sizes": {
                    "val": 1000
                }
            },
            self.version_chk: {
                "required": {
                    "val": self.supporter.keydefaults["val"],
                    "listener": self.supporter.keydefaults["listener"],
                },
                "optional": ["listener"],
                "sizes": {
                    "val": 20
                }
            },
            self.gmsg: {
                "required": {
                    "val": self.supporter.keydefaults["val"],
                    "listener": self.supporter.keydefaults["listener"],
                    "rooms": self.supporter.keydefaults["rooms"]
                },
                "optional": ["listener", "rooms"],
                "sizes": {
                    "val": 1000
                }
            },
            self.link: {
                "required": {
                    "val": self.supporter.keydefaults["rooms"],
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["listener"],
                "sizes": {
                    "val": 1000
                }
            },
            self.unlink: {
                "required": {
                    "val": self.supporter.keydefaults["rooms"],
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["val", "listener"],
                "sizes": {
                    "val": 1000
                }
            },
            self.auth_pswd: {
                "required": {
                    "username": str,
                    "pswd": str,
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["listener"],
                "sizes": {
                    "username": 20,
                    "pswd": 255
                }
            },
            self.gen_account: {
                "required": {
                    "username": str,
                    "pswd": str,
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["listener"],
                "sizes": {
                    "username": 20,
                    "pswd": 255
                }
            },
            self.auth_token: {
                "required": {
                    "token": str,
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["listener"],
                "sizes": {
                    "token": 350
                }
            },
            self.change_pswd: {
                "required": {
                    "pswd": str,
                    "new_pswd": str,
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["listener"],
                "sizes": {
                    "pswd": 255,
                    "new_pswd": 255
                }
            },
            self.del_tokens: {
                "required": {
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["listener"],
                "sizes": {}
            },
            self.del_account: {
                "required": {
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["listener"],
                "sizes": {}
            },
            self.update_config: {
                "required": {
                    "val": self.supporter.keydefaults["val"],
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["listener"],
                "sizes": {
                    "val": 1000
                }
            },
            self.get_profile: {
                "required": {
                    "val": self.supporter.keydefaults["val"],
                    "listener": self.supporter.keydefaults["listener"]
                },
                "optional": ["listener"],
                "sizes": {}
            },
            
        }

        self.log("[Meower CL] Meower CL4 methods initialized!")
    
    # Events for clients

    async def on_connect(self, client):
        # Create attributes for the new client
        client.uuid = ""
        client.authed = False
        client.last_packet = {}
        client.burst_amount = {}
        client.ratelimit = {}
        client.protocol = self.supporter.proto_cloudlink

        self.log(f"[Meower CL] Client {client.id} connected: {client.full_ip}")

        # This should be moved to authentication

        if client.full_ip in self.cached_safe_ips:
            self.log(f"Client {client.id} is a known safe IP")

        else:
            # Verify the client is not using a bad VPN/Proxy
            api_key = os.getenv("IPHUB_KEY", "")

            if not api_key:
                self.log(f"[Meower CL] Could not load API key, assuming client {client.id} IP is safe")
                return
            
            ip_info = requests.get(f"http://v2.api.iphub.info/ip/{client.full_ip}", headers={"X-Key": api_key})
            if ip_info.status_code == 200:
                if ip_info.json()["block"] == 1:
                    self.log(f"[Meower CL] Client {client.id} is connected via VPN/Proxy! ISP: \"{ip_info.json()['isp']}\", Country code: \"{ip_info.json()['countryCode']}\"")

                    # Block the IP address
                    self.server.ip_blocklist.append(client.full_ip)

                    # Alert the client they have been blocked
                    await self.send_code(
                        client = client,
                        code = "NoProxyVPNBlock"
                    )

                    # Kick the client
                    await self.server.reject_client(client, "VPN/Proxy detected")
                    return
            else:
                self.log(f"IPHub error: {ip_info.status_code}")

                # Alert the client that an internal error has occurred
                await self.send_code(
                    client = client,
                    code = "InternalServerError"
                )

                # Kick the client
                await self.server.reject_client(client, "Internal server error")
                return
            
            self.log(f"[Meower CL] Client {client.id} IP is safe")
            self.cached_safe_ips.add(client.full_ip)

    async def on_close(self, client):
        self.log(f"[Meower CL] Client {client.id} disconnected with code {client.close_code} and reason \"{client.close_reason}\"")

    async def __auto_validate__(self, validator, client, message, listener):
        validation = self.supporter.validate(
            keys=validator["required"],
            payload=message,
            optional=validator["optional"],
            sizes=validator["sizes"]
        )

        match validation:
            case self.supporter.invalid:
                # Command datatype is invalid
                await self.send_code(client, "DataType", listener=listener)
                return False

            case self.supporter.missing_key:
                # Command syntax is invalid
                await self.send_code(client, "Syntax", listener=listener)
                return False
            
            case self.supporter.too_large:
                # Payload size overload
                await self.send_code(client, "TooLarge", listener=listener)
                return False

        return True

    # Server overrides

    async def link(self, client, message, listener):
        # Client needs authentication
        if not client.authed:
            await self.send_code(
                client = client,
                code = "IDRequired",
                listener = listener
            )
            return

        # Validate the message syntax and datatypes
        if not await self.__auto_validate__(self.validator[self.link], client, message, listener):
            return

        print("Overriding builtin link command!")
        await self.server.cl_methods.link(client, message, listener)
    
    async def unlink(self, client, message, listener):
        # Client needs authentication
        if not client.authed:
            await self.send_code(
                client = client,
                code = "IDRequired",
                listener = listener
            )
            return
        
        # Validate the message syntax and datatypes
        if not await self.__auto_validate__(self.validator[self.unlink], client, message, listener):
            return

        print("Overriding builtin unlink command!")
        await self.server.cl_methods.unlink(client, message, listener)
    
    async def gmsg(self, client, message, listener):
        # Client needs authentication
        if not client.authed:
            await self.send_code(
                client = client,
                code = "IDRequired",
                listener = listener
            )
            return
        
        # Validate the message syntax and datatypes
        if not await self.__auto_validate__(self.validator[self.gmsg], client, message, listener):
            return
        
        print("Overriding builting gmsg command!")
        await self.server.cl_methods.gmsg(client, message, listener)

    # Authentication and account management

    async def deauth(self, client, message, listener):
        print("Logout account")

        # Requires auth
        if not client.authed:
            await self.send_code(
                client = client,
                code = "IDRequired",
                listener = listener
            )
            return

        # Update the client's authentication state
        client.authed = False

        # Broadcast to all clients that a user has come offline
        if client.friendly_username in self.user_object_shared:
            self.user_object_shared[client.friendly_username].discard(client)

            # Update client states
            if len(self.user_object_shared[username]) == 0:
                await self.server.send_packet_multicast(
                    cmd = "direct",
                    val = {
                        "mode": "offline",
                        "username": username
                    },
                    clients = self.server.clients.get_all_cloudlink()
                )
            
                # Delete the shared username object
                del self.user_object_shared[client.friendly_username]

        # End the session
        await self.send_code(
            client = client,
            code = "OK",
            listener = listener
        )

    async def gen_account(self, client, message, listener):
        print("Generate account")

        # Prevent re-authenticating if client is already authed
        if client.authed:
            await self.send_code(
                client = client,
                code = "IDSet",
                listener = listener
            )
            return
        
        # Validate the message syntax and datatypes
        if not await self.__auto_validate__(self.validator[self.gen_account], client, message["val"], listener):
            return
        
        # Read payload dict keys
        username = message["val"]["username"]
        password = message["val"]["pswd"]

        # Check for invalid chars in the username
        if self.parent.supporter.check_for_bad_chars_username(username):
            # Invalid characters detected
            return
        
        # Ratelimit
        if self.parent.supporter.check_for_spam("authentication", client, burst=2, seconds=120):
            # Ratelimit reached
            return

        # Create the account
        status = self.accounts.create_account(username, password)
        match status:
            # Cannot generate an account that already exists
            case self.accounts.accountExists:
                await self.send_code(
                    client = client,
                    code = "IDExists",
                    listener = listener
                )
                return
            
            # Something went wrong
            case self.accounts.accountIOError:
                await self.send_code(
                    client = client,
                    code = "InternalServerError",
                    listener = listener
                )
                return
            
            case self.accounts.accountCreated:
                
                # Update client authentication state
                client.authed = True
                
                # Manage state
                if username not in self.user_object_shared:
                    self.user_object_shared[username] = set()
                self.user_object_shared[username].add(client)

                # Broadcast to all clients that a user has come online
                if len(self.user_object_shared[username]) == 1:
                    # Update client states
                    await self.server.send_packet_multicast(
                        cmd = "direct",
                        val = {
                            "mode": "online",
                            "username": username
                        },
                        clients = self.server.clients.get_all_cloudlink()
                    )

                # Generate a new session token
                token = self.accounts.create_token(username)
                extra_data = {
                    "mode": "auth",
                    "token": str(token)
                }

                # Return token, valid username, and start session for the client
                await self.parent.supporter.auto_id(
                    client,
                    username,
                    extra_data=extra_data,
                    echo=True
                )

    async def auth_pswd(self, client, message, listener):
        print("Auth pswd")

        # Prevent re-authenticating if client is already authed
        if client.authed:
            await self.send_code(
                client = client,
                code = "IDSet",
                listener = listener
            )
            return

        # Validate the message syntax and datatypes
        if not await self.__auto_validate__(self.validator[self.auth_pswd], client, message["val"], listener):
            return
        
        # Read payload dict keys
        username = message["val"]["username"]
        password = message["val"]["pswd"]

        # Check for invalid chars in the username
        if self.parent.supporter.check_for_bad_chars_username(username):
            # Invalid characters detected
            return
        
        # Ratelimit
        if self.parent.supporter.check_for_spam("authentication", client, burst=2, seconds=120):
            # Ratelimit reached
            return
        
        # Run authentication
        status = self.accounts.authenticate_pswd(username, password)
        match status:
            case self.accounts.accountAuthenticated:
                # Update client authentication state
                client.authed = True

                # Manage state
                if username not in self.user_object_shared:
                    self.user_object_shared[username] = set()
                self.user_object_shared[username].add(client)

                # Broadcast to all clients that a user has come online
                if len(self.user_object_shared[username]) == 1:
                    # Update client states
                    await self.server.send_packet_multicast(
                        cmd = "direct",
                        val = {
                            "mode": "online",
                            "username": username
                        },
                        clients = self.server.clients.get_all_cloudlink()
                    )

                # Generate a new session token
                token = self.accounts.create_token(username)
                extra_data = {
                    "token": str(token)
                }

                # Return token, valid username, and start session for the client
                await self.parent.supporter.auto_id(
                    client,
                    username,
                    extra_data=extra_data,
                    listener=listener,
                    echo = True
                )

            # Invalid password
            case self.accounts.accountNotAuthenticated:
                await self.send_code(
                    client = client,
                    code = "PasswordInvalid",
                    listener = listener
                )
            
            # Account banned
            case self.accounts.accountBanned:
                await self.send_code(
                    client = client,
                    code = "Banned",
                    listener = listener
                )
            
            # Account not found
            case self.accounts.accountDoesNotExist:
                await self.send_code(
                    client = client,
                    code = "IDNotFound",
                    listener = listener
                )
    
    async def auth_token(self, client, message, listener):
        print("Auth token")
    
    async def change_pswd(self, client, message, listener):
        print("Change pswd")
    
    async def del_tokens(self, client, message, listener):
        print("Delete tokens")
    
    async def del_account(self, client, message, listener):
        print("Delete account")
    
    async def update_config(self, client, message, listener):
        print("Update config")

        # Requires auth
        if not client.authed:
            await self.send_code(
                client = client,
                code = "IDRequired",
                listener = listener
            )
            return
        
        # Validate the message syntax and datatypes
        if not await self.__auto_validate__(self.validator[self.update_config], client, message, listener):
            return
        
        # Update the account in the database
        self.log(f"[Meower CL] Updating account config for user {client.friendly_username}")
        result = self.accounts.update_setting(client.friendly_username, message["val"])
        match result:
            # I/O error
            case self.accounts.accountIOError:
                await self.send_code(
                    client = client,
                    code = "InternalServerError",
                    listener = listener
                )
                return

            # Account not found (will likely never trigger because of previous guard clause)
            case self.accounts.accountDoesNotExist:
                await self.send_code(
                    client = client,
                    code = "IDNotFound",
                    listener = listener
                )
                return
        
        # Account config updated successfully
        await self.send_code(
            client = client,
            code = "OK",
            listener = listener
        )

        # Broadcast the updated account state
        result = self.accounts.get_account(client.friendly_username, False, True)

        await self.server.send_packet_multicast(
            cmd = "direct",
            val = {
                "mode": "config_update",
                "payload": result
            },
            clients = self.server.clients.get_all_cloudlink(),
            exclude_client = client
        )
    
    async def get_profile(self, client, message, listener):
        print("Read profile")

        # Method does not require auth
        
        # Validate the message syntax and datatypes
        if not await self.__auto_validate__(self.validator[self.get_profile], client, message, listener):
            return
        
        # Read the account from the database
        result = self.accounts.get_account(message["val"], (message["val"] != client.friendly_username), True)

        # Account does not exist
        if result == self.accounts.accountDoesNotExist:
            await self.send_code(
                client = client,
                code = "IDNotFound",
                listener = listener
            )
            return

        # Prepare payload
        msg = {"val": dict()}
        msg["val"].update(result)
        msg["is_online"] = True
        msg["val"]["is_self"] = (message["val"] == client.friendly_username)

        # Return with payload
        await self.send_code(
            client = client,
            code = "OK",
            extra_data = msg,
            listener = listener
        )
    
    # Basic functionality

    async def get_home(self, client, message, listener):
        print("Get home")

    async def post_home(self, client, message, listener):
        print("Post home")
    
    async def get_post(self, client, message, listener):
        print("Get post")
    
    async def search_user_posts(self, client, message, listener):
        print("Search post")
    
    async def delete_post(self, client, message, listener):
        print("Delete post")
    
    # Chats

    async def create_chat(self, client, message, listener):
        print("Create chat")
    
    async def leave_chat(self, client, message, listener):
        print("Leave chat")
    
    async def get_chat_list(self, client, message, listener):
        print("Get chat list")
    
    async def get_chat_data(self, client, message, listener):
        print("Get chat data")
    
    async def get_chat_posts(self, client, message, listener):
        print("Get chat posts")
    
    async def set_chat_state(self, client, message, listener):
        print("Set chat state")
    
    async def post_chat(self, client, message, listener):
        print("Post chat")
    
    async def add_to_chat(self, client, message, listener):
        print("Add to chat")
    
    async def remove_from_chat(self, client, message, listener):
        print("Remove from chat")
    
    # Inbox / misc

    async def get_inbox(self, client, message, listener):
        print("Get inbox")
    
    async def get_peak_users(self, client, message, listener):
        print("Get peak users")
        
        await self.send_code(
            client = client,
            code = "OK",
            extra_data = {
                "val": self.peak_users_logger
            },
            listener = listener
        )
    
    async def version_chk(self, client, message, listener):
        # Validate the message syntax and datatypes
        if not await self.__auto_validate__(self.validator[self.version_chk], client, message, listener):
            return
        
        self.log(f"[Meower CL] Client {client.id} reports version string \"{message['val']}\"")

        # Load supported versions list
        result, payload = self.db.load_item("config", "supported_versions")
        
        # Handle loading failure
        if not result:
            await self.send_code(
                client = client,
                code = "InternalServerError",
                listener = listener
            )
            return
        
        # Client version invalid/obsolete
        if message["val"] not in payload["index"]:
            await self.send_code(
                client = client,
                code = "ObsoleteClient",
                listener = listener
            )
            return

        # Client version is valid
        await self.send_code(
            client = client,
            code = "OK",
            listener = listener
        )

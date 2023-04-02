from src.common.util import config, validate, errors, security, events
from src.common.entities import users, networks, posts, chats, reports, audit_log


class CL3Commands:
    def __init__(self, cl_server):
        self.cl = cl_server
    
    # CL3 commands
    async def ip(self, client, val, listener): pass  # deprecated
    
    async def type(self, client, val, listener): pass  # deprecated

    async def direct(self, client, val, listener): pass  # deprecated

    async def setid(self, client, val, listener): pass  # deprecated

    async def pmsg(self, client, val, listener):
        # Check if the client is already authenticated
        if not client.username:
            raise errors.NotAuthenticated

        # Validate payload
        validate(val, {"id": (str, None, 20), "val": (None, None, 360)})

        # Ratelimit client
        security.auto_ratelimit(client.username, "pmsg", 10, 5)

        # Send pmsg event
        events.send_event("pmsg", {
            "username": val["id"],
            "origin": client.username,
            "val": val["val"]
        })

    async def pvar(self, client, val, listener):
        # Check if the client is already authenticated
        if not client.username:
            raise errors.NotAuthenticated

        # Validate payload
        validate(val, {"id": (str, None, 20), "name": (None, None, 360), "val": (None, None, 360)})

        # Ratelimit client
        security.auto_ratelimit(client.username, "pvar", 10, 5)

        # Send pvar event
        events.send_event("pvar", {
            "username": val["id"],
            "origin": client.username,
            "name": val["name"],
            "val": val["val"]
        })

    # Networking/client utilities

    async def ping(self, client, val, listener): pass

    async def version_chk(self, client, val, listener): pass # deprecated
    
    async def get_ulist(self, client, val, listener):
        await self.cl.send_to_client(client, {"cmd": "ulist", "val": self.cl.ulist}, listener)

    async def get_peak_users(self, client, val, listener):
        await self.cl.send_to_client(client, {
            "cmd": "direct",
            "val": {
                "mode": "peak",
                "payload": self.cl.peak_users
            }
        }, listener)

    # Accounts and security
    
    async def authpswd(self, client, val, listener):
        # Check if the client is already authenticated
        if client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"username": (str, None, 20), "pswd": (str, None, 255)})
        
        # Extract username and password
        username = val["username"]
        password = val["pswd"]
        
        # Check whether client is ratelimited
        if security.check_ratelimit(client.ip, "login"):
            raise errors.Ratelimited

        # Get user
        user = users.get_user(username)
        
        # Check whether user is banned
        if user.banned:
            raise errors.UserBanned

        # Check token/password and get new token
        if user.validate_token(password):
            token = password
        elif user.check_password(password):
            token = user.generate_token()
        else:
            security.ratelimit(client.ip, "login", 5, 60)
            raise errors.InvalidPassword

        # Log current network
        network = networks.get_network(client.ip)
        network.log_user(user.username)

        # Cancel scheduled account deletion
        if user.delete_after:
            user.cancel_scheduled_deletion()

        # Authenticate client
        client.username = user.username
        if user.invisible:
            self.cl.invisible_users.add(user.username)
        if client.username not in self.cl.users:
            self.cl.users[client.username] = set()
        self.cl.users[client.username].add(client)

        # Subscribe to chats
        for chat_id in chats.get_all_chat_ids(client.username):
            self.cl.subscribe_to_chat(client, chat_id)

        # Return payload to client
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
        await self.cl.log_peak_users()
    
    async def gen_account(self, client, val, listener):
        # Check if the client is already authenticated
        if client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"username": (str, 1, 20), "pswd": (str, 8, 255)})
        
        # Extract username and password
        username = val["username"]
        password = val["pswd"]
        
        # Check whether client is ratelimited
        if security.check_ratelimit(client.ip, "register"):
            raise errors.Ratelimited

        # Check whether network is a proxy
        network = networks.get_network(client.ip)
        if config.block_proxies and network.proxy:
            raise errors.IPBanned

        # Create user account
        user = users.create_user(username, password)

        # Ratelimit client
        security.ratelimit(client.ip, "register", 2, 120)

        # Generate token
        token = user.generate_token()

        # Log current network
        network.log_user(user.username)

        # Authenticate client
        client.username = user.username
        if user.invisible:
            self.cl.invisible_users.add(user.username)
        if client.username not in self.cl.users:
            self.cl.users[client.username] = set()
        self.cl.users[client.username].add(client)

        # Subscribe to chats
        for chat_id in chats.get_all_chat_ids(client.username):
            self.cl.subscribe_to_chat(client, chat_id)

        # Return payload to client
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
        await self.cl.log_peak_users()

    async def get_profile(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated

        # Validate payload
        validate({"val": val}, {"val": (str, None, 20)})

        # Get user
        user = users.get_user(val)
        
        # Return profile
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "profile",
                "payload": (user.client if (client.username == user.username) else user.public),
                "user_id": user.username
            }
        }
        await self.cl.send_to_client(client, payload, listener)
    
    async def update_config(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated

        # Check datatype
        if not isinstance(val, dict):
            raise errors.InvalidDatatype

        # Get user
        user = users.get_user(client.username)
        
        # Update the config
        user.update_config(val)
    
    async def change_pswd(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated

        # Validate payload
        validate(val, {"old": (str, None, 255), "new": (str, 8, 255)})
        
        # Check whether client is ratelimited
        if security.check_ratelimit(client.username, "login"):
            raise errors.Ratelimited

        # Get user
        user = users.get_user(client.username)

        # Check old password
        if not user.check_password(val["old"]):
            security.ratelimit(client.username, "login", 5, 60)
            raise errors.InvalidPassword
        
        # Set new password
        user.change_password(val["new"])
    
    async def del_tokens(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Get user
        user = users.get_user(client.username)
        
        # Revoke sessions
        user.revoke_sessions()
    
    async def del_account(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 255)})
        
        # Get user
        user = users.get_user(client.username)

        # Check password
        if not user.check_password(val):
            raise errors.InvalidPassword
        
        # Schedule account for deletion
        user.schedule_deletion()

    # General

    async def get_inbox(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.MissingPermissions
        
        # Validate payload
        validate(val, {"page": (int, 1, None)}, optional=["page"])

        # Extract page
        if isinstance(val, dict):
            page = val.get("page", 1)
        else:
            page = 1

        # Get inbox index
        pages, fetched_posts = posts.get_inbox_messages(client.username, page=page)

        # Return inbox index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "inbox",
                "payload": {
                    "index": [post.id for post in fetched_posts],
                    "page#": page,
                    "pages": pages,
                    "query": {
                        "origin": "inbox",
                        "deleted_at": None,
                        "author": {"$in": [client.username, "Server"]}
                    }
                }
            }
        }
        await self.cl.send_to_client(client, payload, listener)
    
    async def get_home(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"page": (int, 1, None)}, optional=["page"])

        # Extract page
        if isinstance(val, dict):
            page = val.get("page", 1)
        else:
            page = 1

        # Get home posts
        pages, fetched_posts = posts.get_posts("home", page=page)

        # Return home index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "home",
                "payload": {
                    "index": [post.id for post in fetched_posts],
                    "page#": page,
                    "pages": pages,
                    "query": {
                        "origin": "home",
                        "deleted_at": None
                    }
                }
            }
        }
        await self.cl.send_to_client(client, payload, listener)
    
    async def post_home(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, 1, 4000)})

        # Ratelimit client
        security.auto_ratelimit(client.username, "post", 5, 5)

        # Create post
        posts.create_post("home", client.username, val)
    
    async def get_post(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 36)})

        # Get post
        post = posts.get_post(val)
        
        # Check if user has permission to access the post
        if not post.has_access(client.username):
            raise errors.NotFound

        # Return post
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "post",
                "payload": post.public
            }
        }
        await self.cl.send_to_client(client, payload, listener)
    
    async def delete_post(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 36)})

        # Get post
        post = posts.get_post(val)
        
        # Get user
        user = users.get_user(client.username)

        # Check whether the client can delete the post
        if (client.username != post.author) and (user.lvl < 1):
            raise errors.MissingPermissions

        # Delete the post
        post.delete(client.username)

    # Logging and data management

    async def search_user_posts(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"query": (str, None, 20), "page": (int, 1, None)}, optional=["page"])

        # Extract username and page
        username = val["query"]
        page = val.get("page", 1)

        # Make sure user exists
        if not users.username_exists(username):
            raise errors.NotFound

        # Get user posts
        pages, fetched_posts = posts.get_posts("home", author=username, page=page)

        # Return user posts index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "user_posts",
                "index": {
                    "index": [post.id for post in fetched_posts],
                    "page#": page,
                    "pages": pages,
                    "query": {
                        "origin": "home",
                        "deleted_at": None,
                        "author": username
                    }
                }
            }
        }
        await self.cl.send_to_client(client, payload, listener)
    
    # Moderator features

    async def report(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"type": (int, 0, 1), "id": (str, None, 36)})

        # Get user
        user = users.get_user(client.username)
        
        # Create report
        reports.create_report(val["type"], val["id"], user.username, user.report_reputation)

    async def close_report(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 36)})

        # Get user
        user = users.get_user(client.username)
        
        # Check user level
        if user.lvl < 1:
            raise errors.MissingPermissions

        # Get report
        report = reports.get_report(val)

        # Close report
        report.close(False)

    async def clear_home(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"page": (int, 1, None)}, optional=["page"])

        # Extract page
        page = val.get("page", 1)

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 1:
            raise errors.MissingPermissions
        
        # Get home page
        pages, fetched_posts = posts.get_posts("home", page=page)

        # Delete all fetched posts
        for post in fetched_posts:
            post.delete(client.username)
    
    async def clear_user_posts(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 20)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 1:
            raise errors.MissingPermissions

        # Get user
        user = users.get_user(val)

        # Clear user's posts
        user.clear_posts(moderator=client.username)

    async def get_user_data(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 20)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 1:
            raise errors.MissingPermissions
        
        # Get user
        user = users.get_user(val)

        # Return user data
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "user_data",
                "payload": user.client
            }
        }
        await self.cl.send_to_client(client, payload, listener)

        # Create audit log item
        audit_log.create_log("get_user_data", client.username, {
            "username": val
        })

    async def alert(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"username": (str, None, 20), "p": (str, 1, 4000)})
        
        # Extract username and content
        username = val["username"]
        content = val["p"]

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 1:
            raise errors.MissingPermissions

        # Get user
        user = users.get_user(username)
        
        # Alert user
        user.alert(content, moderator=client.username)
    
    async def kick(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 20)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 1:
            raise errors.MissingPermissions
        
        # Get user
        user = users.get_user(val)
        
        # Kick user
        user.kick(moderator=client.username)

    async def ban(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        if isinstance(val, str):
            validate({"val": val}, {"val": (str, None, 20)})
        else:
            validate(val, {"username": (str, None, 20), "expires": (int, None, None)})

        # Extract username and expires
        if isinstance(val, str):
            username = val
            expires = -1
        else:
            username = val["username"]
            expires = val["expires"]

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 1:
            raise errors.MissingPermissions
        
        # Get user
        user = users.get_user(username)

        # Ban user
        user.ban(expires, moderator=client.username)
    
    async def pardon(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 20)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 1:
            raise errors.MissingPermissions
        
        # Get user
        user = users.get_user(val)

        # Unban user
        user.unban()
    
    async def terminate(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 20)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 3:
            raise errors.MissingPermissions
        
        # Get user
        user = users.get_user(val)

        # Terminate user
        user.terminate(moderator=client.username)

    async def gdpr(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 20)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 4:
            raise errors.MissingPermissions
        
        # Get user
        user = users.get_user(val)

        # Schedule user for deletion
        user.schedule_deletion(delay=0)

    async def get_ip_data(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, 1, 64)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 2:
            raise errors.MissingPermissions
        
        # Get network
        network = networks.get_network(val)

        # Return network data
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "ip_data",
                "payload": network.admin
            }
        }
        await self.cl.send_to_client(client, payload, listener)

        # Create audit log item
        audit_log.create_log("get_ip_data", client.username, {
            "ip": val
        })

    async def block(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, 1, 64)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 2:
            raise errors.MissingPermissions
        
        # Get network
        network = networks.get_network(val)

        # Ban network
        network.set_ban_state(True)

    async def unblock(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, 1, 64)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 2:
            raise errors.MissingPermissions
        
        # Get network
        network = networks.get_network(val)

        # Unban network
        network.set_ban_state(False)

    async def get_user_ip(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 20)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 2:
            raise errors.MissingPermissions
        
        # Get user
        user = users.get_user(val)

        # Return user IP
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "user_ip",
                "payload": {
                    "username": user.username,
                    "ip": user.last_ip
                }
            }
        }
        await self.cl.send_to_client(client, payload, listener)

    async def ip_ban(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, 1, 64)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 2:
            raise errors.MissingPermissions
        
        # Get user
        user = users.get_user(val)

        # Get network
        network = networks.get_network(user.last_ip)

        # Ban network
        network.set_ban_state(True)

    async def ip_pardon(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, 1, 64)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 2:
            raise errors.MissingPermissions
        
        # Get user
        user = users.get_user(val)

        # Get network
        network = networks.get_network(user.last_ip)

        # Unban network
        network.set_ban_state(False)

    async def announce(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, 1, 4000)})

        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 3:
            raise errors.MissingPermissions
        
        # Create announcement
        posts.create_announcement(val)

        # Create audit log item
        audit_log.create_log("create_announcement", client.username, {
            "content": val
        })

    async def repair_mode(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Get user
        user = users.get_user(client.username)

        # Check user level
        if user.lvl < 4:
            raise errors.MissingPermissions
        
        # Enable repair mode
        events.send_event("update_server", {"repair_mode": True})

        # Create audit log item
        audit_log.create_log("enable_repair_mode", client.username, {})

    # Chat-related
    
    async def get_chat_list(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"page": (int, 1, None)}, optional=["page"])

        # Extract page
        if isinstance(val, dict):
            page = val.get("page", 1)
        else:
            page = 1

        # Get chats
        pages, user_chats = chats.get_users_chats(client.username, page=page)

        # Return chats index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "chats",
                "payload": {
                    "index": [chat.id for chat in user_chats],
                    "all_chats": [chat.public for chat in user_chats],
                    "page#": page,
                    "pages": pages,
                    "query": {
                        "members": {
                            "$all": [client.username]
                        }
                    }
                }
            }
        }
        await self.cl.send_to_client(client, payload, listener)

    async def create_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, 1, 20)})

        # Ratelimit client
        security.auto_ratelimit(client.username, "chat", 5, 3)

        # Create chat
        chats.create_chat(val, client.username)
    
    async def join_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, 7, 7)})

        # Get chat
        chat = chats.get_chat_by_invite_code(val)

        # Ratelimit client
        security.auto_ratelimit(client.username, "chat", 5, 3)

        # Add client to the chat
        try:
            chat.add_member(client.username, client.username)
        except errors.AlreadyExists:
            pass

    async def leave_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 36)})

        # Get chat
        chat = chats.get_chat(val)

        # Check if the client is in the chat
        if client.username not in chat.members:
            raise errors.NotFound

        # Remove member from the chat
        chat.remove_member(client.username, client.username)
    
    async def get_chat_data(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 36)})

        # Get chat
        chat = chats.get_chat(val)

        # Check if the client is in the chat
        if client.username not in chat.members:
            raise errors.NotFound

        # Return chat data
        chat_json = chat.public
        chat_json["chatid"] = chat_json.pop("_id")
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "chat_data",
                "payload": chat_json
            }
        }
        await self.cl.send_to_client(client, payload, listener)

    async def edit_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"chatid": (str, None, 36), "nickname": (str, 1, 20), "owner": (str, None, 20), "invite_code": (bool, None, None)}, optional=["nickname", "owner", "invite_code"])

        # Ratelimit client
        security.auto_ratelimit(client.username, "chat", 5, 3)

        # Get chat
        chat = chats.get_chat(val["chatid"])

        # Check if the client is in the chat
        if client.username not in chat.members:
            raise errors.NotFound

        # Check if the client is the owner of the chat
        if client.username != chat.owner:
            raise errors.MissingPermissions

        # Change nickname
        if val.get("nickname"):
            chat.change_nickname(val["nickname"])
        
        # Transfer ownership
        if val.get("owner"):
            chat.change_owner(val["owner"], actor=client.username)

        # Reset invite code
        if val.get("invite_code"):
            chat.reset_invite_code()

    async def delete_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate({"val": val}, {"val": (str, None, 36)})

        # Get chat
        chat = chats.get_chat(val)

        # Check if the client is in the chat
        if client.username not in chat.members:
            raise errors.NotFound

        # Check if the client is the owner of the chat
        if client.username != chat.owner:
            raise errors.MissingPermissions

        # Delete chat
        chat.delete()

    async def add_to_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"chatid": (str, None, 36), "username": (str, None, 20)})

        # Ratelimit client
        security.auto_ratelimit(client.username, "chat", 5, 3)

        # Get chat
        chat = chats.get_chat(val["chatid"])

        # Check if the client is in the chat
        if client.username not in chat.members:
            raise errors.NotFound

        # Add member to chat
        chat.add_member(val["username"], client.username)

    async def remove_from_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"chatid": (str, None, 36), "username": (str, None, 20)})

        # Ratelimit client
        security.auto_ratelimit(client.username, "chat", 5, 3)

        # Get chat
        chat = chats.get_chat(val["chatid"])

        # Check if the client is in the chat
        if client.username not in chat.members:
            raise errors.NotFound
        
        # Check if the client is the owner of the chat
        if client.username != chat.owner:
            raise errors.MissingPermissions

        # Remove member from chat
        chat.remove_member(val["username"], client.username)

    async def set_chat_state(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"chatid": (str, None, 36), "state": (int, None, None)})

        # Ratelimit client
        security.auto_ratelimit(client.username, "chat", 5, 3)

        # Get chat
        chat = chats.get_chat(val["chatid"])

        # Check if the client is in the chat
        if (chat.id != "livechat") and (client.username not in chat.members):
            raise errors.NotFound
        
        # Broadcast new chat state
        chat.set_chat_state(client.username, val["state"])
    
    async def get_chat_posts(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated

        # Validate payload
        validate({"val": val}, {"val": (str, None, 36)})

        # Get chat
        chat = chats.get_chat(val)

        # Check if the client is in the chat
        if client.username not in chat.members:
            raise errors.NotFound

        # Get posts index
        pages, fetched_posts = posts.get_posts(chat.id, page=1)

        # Return posts index
        payload = {
            "cmd": "direct",
            "val": {
                "mode": "chat_posts",
                "payload": {
                    "index": [post.id for post in fetched_posts],
                    "page#": 1,
                    "pages": pages,
                    "query": {
                        "origin": chat.id,
                        "deleted_at": None
                    }
                }
            }
        }
        await self.cl.send_to_client(client, payload, listener)

    async def post_chat(self, client, val, listener):
        # Check if the client is authenticated
        if not client.username:
            raise errors.NotAuthenticated
        
        # Validate payload
        validate(val, {"chatid": (str, None, 36), "p": (str, 1, 4000)})

        # Ratelimit client
        security.auto_ratelimit(client.username, "post", 5, 5)

        # Get chat
        chat = chats.get_chat(val["chatid"])

        # Check if the client is in the chat
        if (chat.id != "livechat") and (client.username not in chat.members):
            raise errors.NotFound

        # Create post
        posts.create_post(chat.id, client.username, val["p"])

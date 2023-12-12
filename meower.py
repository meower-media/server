import time
import uuid
import secrets
import pymongo
from dotenv import load_dotenv
from threading import Thread
import bcrypt
import re

from security import UserFlags, Restrictions

load_dotenv()  # take environment variables from .env.

class Meower:
    def __init__(self, cl, supporter, logger, errorhandler, security, files):
        self.cl = cl
        self.supporter = supporter
        self.log = logger
        self.errorhandler = errorhandler
        self.security = security
        self.files = files
        self.sendPacket = self.supporter.sendPacket

        # Load netblocks
        for netblock in self.files.db.netblock.find({}):
            try:
                if netblock["type"] == 0:
                    self.supporter.blocked_ips.add(netblock["_id"])
                elif netblock["type"] == 1:
                    self.supporter.registration_blocked_ips.add(netblock["_id"])
            except Exception as e:
                self.log("Failed to load netblock {0}: {1}".format(netblock["_id"], e))
        self.log(f"Successfully loaded {len(self.supporter.blocked_ips.nodes())} netblock(s) into Radix!")
        self.log(f"Successfully loaded {len(self.supporter.registration_blocked_ips.nodes())} registration netblock(s) into Radix!")

        # Load filter
        self.supporter.filter = self.files.db.config.find_one({"_id": "filter"})
        del self.supporter.filter["_id"]

        # Load status
        status = self.files.db.config.find_one({"_id": "status"})
        self.supporter.repair_mode = status["repair_mode"]
        self.supporter.registration = status["registration"]

        self.log("Meower initialized!")



    # Some Meower-library specific utilities needed

    def returnCode(self, client, code, listener_detected, listener_id):
        self.sendPacket({"cmd": "statuscode", "val": self.cl.codes[str(code)], "id": client}, listener_detected = listener_detected, listener_id = listener_id)



    # Networking/client utilities
    
    def ping(self, client, val, listener_detected, listener_id):
        # Returns your ping for my pong
        self.returnCode(client = client, code = "Pong", listener_detected = listener_detected, listener_id = listener_id)
    
    def get_ulist(self, client, val, listener_detected, listener_id):
        self.sendPacket({"cmd": "ulist", "val": self.cl._get_ulist(), "id": client}, listener_detected = listener_detected, listener_id = listener_id)



    # Accounts and security
    
    def authpswd(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check val datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check val syntax
        if ("username" not in val) or ("pswd" not in val):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract username, password, and IP
        username = val["username"]
        password = val["pswd"]
        ip = self.supporter.get_client_statedata(client)[0]["ip"]

        # Check username and password datatypes
        if (not isinstance(username, str)) or (not isinstance(password, str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check username and password syntax
        if len(username) < 1 or len(username) > 20 or len(password) < 1 or len(password) > 255:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimits
        for bucket_id in [
            f"login:i:{ip}",
            f"login:u:{username}:s",
            f"login:u:{username}:f"
        ]:
            if self.supporter.ratelimited(bucket_id):
                return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
        
        # Ratelimit IP
        self.supporter.ratelimit(f"login:i:{ip}", 100, 1800)

        # Get tokens, password, permissions, ban state, and delete after timestamp
        account = self.files.db.usersv0.find_one({"_id": username}, projection={
            "tokens": 1,
            "pswd": 1,
            "flags": 1,
            "permissions": 1,
            "ban": 1,
            "delete_after": 1
        })
        if not account:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        elif (account["flags"] & UserFlags.DELETED == UserFlags.DELETED) or (account["delete_after"] and account["delete_after"] <= time.time()+60):
            self.supporter.ratelimit(f"login:u:{username}:f", 5, 60)
            return self.returnCode(client = client, code = "Deleted", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check password
        if (password not in account["tokens"]) and (not bcrypt.checkpw(password.encode(), account["pswd"].encode())):
            self.supporter.ratelimit(f"login:u:{username}:f", 5, 60)
            return self.returnCode(client = client, code = "PasswordInvalid", listener_detected = listener_detected, listener_id = listener_id)
        
        # Update netlog
        netlog_result = self.files.db.netlog.update_one({"_id": {"ip": ip, "user": username}}, {"$set": {"last_used": int(time.time())}}, upsert=True)

        # Check ban
        if (account["ban"]["state"] == "perm_ban") or (account["ban"]["state"] == "temp_ban" and account["ban"]["expires"] > time.time()):
            self.supporter.ratelimit(f"login:u:{username}:f", 5, 60)
            self.sendPacket({"cmd": "direct", "val": {
                "mode": "banned",
                "payload": account["ban"]
            }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"login:u:{username}:s", 25, 300)

        # Alert user of new IP address if user has admin permissions
        if account["permissions"] and netlog_result.upserted_id:
            self.supporter.createPost("inbox", username, f"Your account was logged into on a new IP address ({ip})! You are receiving this message because you have admin permissions. Please make sure to keep your account secure.")
        
        # Alert user if account was pending deletion
        if account["delete_after"]:
            self.supporter.createPost("inbox", username, f"Your account was scheduled for deletion but you logged back in. Your account is no longer scheduled for deletion! If you didn't request for your account to be deleted, please change your password immediately.")

        # Generate new token
        token = secrets.token_urlsafe(64)

        # Update user
        self.files.db.usersv0.update_one({"_id": username}, {
            "$addToSet": {"tokens": token},
            "$set": {
                "last_seen": int(time.time()),
                "delete_after": None
            }
        })

        # Set client authenticated state
        self.supporter.autoID(client, username) # Give the client an AutoID
        self.supporter.setAuthenticatedState(client, True) # Make the server know that the client is authed

        # Get relationships
        relationships = [{
            "username": relationship["_id"]["to"],
            "state": relationship["state"],
            "updated_at": relationship["updated_at"]
        } for relationship in self.files.db.relationships.find({"_id.from": username})]

        # Return info to sender
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "auth",
            "payload": {
                "username": username,
                "token": token,
                "account": self.security.get_account(username, True),
                "relationships": relationships
            }
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        
        # Tell the client it is authenticated
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
    
    def gen_account(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        
        # Make sure registration isn't disabled
        if not self.supporter.registration:
            return self.returnCode(client = client, code = "Disabled", listener_detected = listener_detected, listener_id = listener_id)

        # Check val datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check val syntax
        if ("username" not in val) or ("pswd" not in val):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract username, password, and IP
        username = val["username"]
        password = val["pswd"]
        ip = self.supporter.get_client_statedata(client)[0]["ip"]

        # Check username and password datatypes
        if (not isinstance(username, str)) or (not isinstance(password, str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check username and password syntax
        if len(username) < 1 or len(username) > 20 or len(password) < 8 or len(password) > 255:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check username regex
        if not re.fullmatch("[a-zA-Z0-9-_]{1,20}", username):
            return self.returnCode(client = client, code = "IllegalChars", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"registration:{ip}:f") or self.supporter.ratelimited(f"registration:{ip}:s"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Check whether IP is blocked from creating new accounts
        if self.supporter.registration_blocked_ips.search_best(ip):
            self.supporter.ratelimit(f"registration:{ip}:f", 5, 30)
            return self.returnCode(client = client, code = "Blocked", listener_detected = listener_detected, listener_id = listener_id)

        # Make sure username doesn't already exist
        if self.security.account_exists(username, ignore_case=True):
            self.supporter.ratelimit(f"registration:{ip}:f", 5, 30)
            return self.returnCode(client = client, code = "IDExists", listener_detected = listener_detected, listener_id = listener_id)

        # Generate new token
        token = secrets.token_urlsafe(64)

        # Create account
        self.files.db.usersv0.insert_one({
            "_id": username,
            "lower_username": username.lower(),
            "uuid": str(uuid.uuid4()),
            "created": int(time.time()),
            "pfp_data": 2,
            "custom_pfp": None,
            "quote": "",
            "pswd": bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=14)).decode(),
            "tokens": [token],
            "flags": 0,
            "permissions": 0,
            "ban": {
                "state": "none",
                "restrictions": 0,
                "expires": 0,
                "reason": ""
            },
            "last_seen": int(time.time()),
            "delete_after": None
        })
        self.files.db.user_settings.insert_one({"_id": username})

        # Ratelimit
        self.supporter.ratelimit(f"registration:{ip}:s", 5, 900)

        # Update netlog
        self.files.db.netlog.update_one({"_id": {"ip": ip, "user": username}}, {"$set": {"last_used": int(time.time())}}, upsert=True)

        # Send welcome message
        self.supporter.createPost("inbox", username, "Welcome to Meower! We welcome you with open arms! You can get started by making friends in the global chat or home, or by searching for people and adding them to a group chat. We hope you have fun!")

        # Set client authenticated state
        self.supporter.autoID(client, username) # Give the client an AutoID
        self.supporter.setAuthenticatedState(client, True) # Make the server know that the client is authed

        # Return info to sender
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "auth",
            "payload": {
                "username": username,
                "token": token,
                "account": self.security.get_account(username, True),
                "relationships": []
            }
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        
        # Tell the client it is authenticated
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

        # Auto-report if client is on a VPN
        if self.security.get_netinfo(ip)["vpn"]:
            self.files.db.reports.insert_one({
                "_id": str(uuid.uuid4()),
                "type": "user",
                "content_id": username,
                "status": "pending",
                "escalated": False,
                "reports": [{
                    "user": "Server",
                    "ip": ip,
                    "reason": "User registered while using a VPN.",
                    "comment": "",
                    "time": int(time.time())
                }]
            })

    def get_profile(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) > 20:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get profile
        account = self.security.get_account(val, (val.lower() == client.lower()))
        if not account:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        
        # Return profile
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "profile",
            "payload": account,
            "user_id": account["_id"]
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def update_config(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

        # Check datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)

        # Check ratelimit
        if self.supporter.ratelimited(f"config:{client}"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"config:{client}", 10, 5)

        # Confirm custom pfp
        if "custom_pfp" in val:
            if val["custom_pfp"] is not None:
                try:
                    upload_details = self.supporter.confirm_upload("icon", val["custom_pfp"], client)
                    if upload_details["uploaded_by"] != client:
                        raise Exception("Uploader doesn't match client")
                except Exception as e:
                    self.log(e)
                    return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    val["custom_pfp"] = upload_details["filename"]

        # Delete quote if client is restricted
        if "quote" in val:
            if self.security.is_restricted(client, Restrictions.EDITING_QUOTE):
                del val["quote"]
        
        # Update config
        FileWrite = self.security.update_settings(client, val)
        if not FileWrite:
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        
        # Sync config between sessions
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "update_config",
            "payload": val
        }, "id": client})

        # Tell the client the config was updated
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def change_pswd(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check val datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check val syntax
        if ("old" not in val) or ("new" not in val):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract old password and new password
        old_pswd = val["old"]
        new_pswd = val["new"]

        # Check old password and new password datatypes
        if (not isinstance(old_pswd, str)) or (not isinstance(new_pswd, str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check old password and new password syntax
        if len(old_pswd) < 1 or len(old_pswd) > 255 or len(new_pswd) < 8 or len(new_pswd) > 255:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"login:u:{client}:f"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"login:u:{client}:f", 5, 60)

        # Check password
        account = self.files.db.usersv0.find_one({"_id": client}, projection={"pswd": 1})
        if not account:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        elif not bcrypt.checkpw(old_pswd.encode(), account["pswd"].encode()):
            return self.returnCode(client = client, code = "PasswordInvalid", listener_detected = listener_detected, listener_id = listener_id)
        
        # Update password
        self.files.db.usersv0.update_one({"_id": client}, {"$set": {
            "pswd": bcrypt.hashpw(new_pswd.encode(), bcrypt.gensalt(rounds=14)).decode()
        }})

        # Tell the client the password was updated
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def del_tokens(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Revoke tokens
        self.files.db.usersv0.update_one({"_id": client}, {"$set": {"tokens": []}})
        
        # Tell the client the tokens were revoked
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

        # Disconnect the user
        time.sleep(1)
        self.supporter.kickUser(client, "LoggedOut")

    def del_account(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) < 1 or len(val) > 255:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"login:u:{client}:f"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"login:u:{client}:f", 5, 60)
        
        # Check password
        account = self.files.db.usersv0.find_one({"_id": client}, projection={"pswd": 1})
        if not bcrypt.checkpw(val.encode(), account["pswd"].encode()):
            return self.returnCode(client = client, code = "PasswordInvalid", listener_detected = listener_detected, listener_id = listener_id)

        # Schedule account for deletion
        self.files.db.usersv0.update_one({"_id": client}, {"$set": {
            "tokens": [],
            "delete_after": int(time.time())+604800  # 7 days
        }})

        # Tell the client their account was scheduled for deletion
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

        # Kick client
        time.sleep(1)
        self.supporter.kickUser(client, "LoggedOut")



    # Group chats/DMs

    def create_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"create_chat:{client}"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"create_chat:{client}", 5, 30)

        # Check restrictions
        if self.security.is_restricted(client, Restrictions.NEW_CHATS):
            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)

        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) < 1 or len(val) > 50:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Make sure the client isn't in too many chats
        if self.files.db.chats.count_documents({"type": 0, "members": client}, limit=150) >= 150:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Create chat
        chat = {
            "_id": str(uuid.uuid4()),
            "type": 0,
            "nickname": self.supporter.wordfilter(val),
            "owner": client,
            "members": [client],
            "created": int(time.time()),
            "last_active": int(time.time()),
            "deleted": False
        }
        self.files.db.chats.insert_one(chat)

        # Tell the client the chat was created
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "create_chat",
            "payload": chat
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def leave_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"update_chat:{client}"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"update_chat:{client}", 5, 5)

        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) < 1 or len(val) > 50:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Get chat
        chat = self.files.db.chats.find_one({"_id": val, "members": client, "deleted": False})
        if not chat:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        if chat["type"] == 0:
            # Remove member
            chat["members"].remove(client)

            # Update chat if it's not empty, otherwise delete the chat
            if len(chat["members"]) > 0:
                # Transfer ownership, if owner
                if chat["owner"] == client:
                    chat["owner"] = chat["members"][0]
                
                # Update chat
                self.files.db.chats.update_one({"_id": val}, {
                    "$set": {"owner": chat["owner"]},
                    "$pull": {"members": client}
                })

                # Send update chat event
                self.sendPacket({"cmd": "direct", "val": {
                    "mode": "update_chat",
                    "payload": {
                        "_id": val,
                        "owner": chat["owner"],
                        "members": chat["members"]
                    }
                }, "id": chat["members"]})

                # Send in-chat notification
                self.supporter.createPost(val, "Server", f"@{client} has left the group chat.", chat_members=chat["members"])
            else:
                self.files.db.posts.delete_many({"post_origin": val, "isDeleted": False})
                self.files.db.chats.delete_one({"_id": val})
        elif chat["type"] == 1:
            # Remove chat from client's active DMs list
            self.files.db.user_settings.update_one({"_id": client}, {
                "$pull": {"active_dms": val}
            })
        else:
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)

        # Send delete event to client
        self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": chat["_id"]}, "id": client})

        # Tell the client it left the chat
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def get_chat_list(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get page
        page = 1
        if isinstance(val, dict):
            try:
                page = int(val["page"])
            except: pass

        # Get chats
        query = {"members": client, "type": 0}
        chats = list(self.files.db.chats.find(query, skip=(page-1)*25, limit=25))

        # Return chats
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "chats",
            "payload": {
                "all_chats": chats,
                "index": [chat["_id"] for chat in chats],
                "page#": page,
                "pages": self.files.get_total_pages("chats", query)
            }
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
    
    def get_chat_data(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) < 1 or len(val) > 50:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get chat
        chat = self.files.db.chats.find_one({"_id": val, "members": client, "deleted": False})
        if not chat:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        
        # Return chat
        chat["chatid"] = chat["_id"]
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "chat_data",
            "payload": chat
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def add_to_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"update_chat:{client}"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"update_chat:{client}", 5, 5)

        # Check restrictions
        if self.security.is_restricted(client, Restrictions.NEW_CHATS):
            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)

        # Check val datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)

        # Check val syntax
        if ("chatid" not in val) or ("username" not in val):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Extract chatid and username
        chatid = val.get("chatid")
        username = val.get("username")

        # Check chatid and username datatypes
        if (not isinstance(chatid, str)) or (not isinstance(username, str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check chatid and username syntax
        if (len(chatid) > 50) or (len(username) > 20):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Get chat
        chat = self.files.db.chats.find_one({"_id": chatid, "members": client, "deleted": False})
        if not chat:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        # Make sure the chat isn't full
        if chat["type"] == 1 or len(chat["members"]) >= 256:
            return self.returnCode(client = client, code = "ChatFull", listener_detected = listener_detected, listener_id = listener_id)
        
        # Make sure the user isn't already in the chat
        if username in chat["members"]:
            return self.returnCode(client = client, code = "IDExists", listener_detected = listener_detected, listener_id = listener_id)

        # Make sure requested user exists and isn't deleted
        user = self.files.db.usersv0.find_one({"_id": username}, projection={"permissions": 1})
        if (not user) or (user["permissions"] is None):
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        # Make sure requested user isn't blocked or is blocking client
        if self.files.db.relationships.count_documents({"$or": [
            {
                "_id": {"from": client, "to": username},
                "state": 2
            },
            {
                "_id": {"from": username, "to": client},
                "state": 2
            }
        ]}, limit=1) > 0:
            return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)

        # Update chat
        chat["members"].append(username)
        self.files.db.chats.update_one({"_id": chatid}, {"$addToSet": {"members": username}})

        # Send create chat event
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "create_chat",
            "payload": chat
        }, "id": username})

        # Send update chat event
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "update_chat",
            "payload": {
                "_id": chatid,
                "members": chat["members"]
            }
        }, "id": chat["members"]})

        # Send inbox message to user
        self.supporter.createPost("inbox", username, f"You have been added to the group chat '{chat['nickname']}' by @{client}!")

        # Send in-chat notification
        self.supporter.createPost(chatid, "Server", f"@{client} added @{username} to the group chat.", chat_members=chat["members"])

        # Tell the client the user was added
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def remove_from_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check val datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)

        # Check val syntax
        if ("chatid" not in val) or ("username" not in val):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Extract chatid and username
        chatid = val.get("chatid")
        username = val.get("username")

        # Check chatid and username datatypes
        if (not isinstance(chatid, str)) or (not isinstance(username, str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check chatid and username syntax
        if (len(chatid) > 50) or (len(username) > 20):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"update_chat:{client}"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"update_chat:{client}", 5, 5)

        # Get chat
        chat = self.files.db.chats.find_one({
            "_id": chatid,
            "members": {"$all": [client, username]},
            "deleted": False
        })
        if not chat:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        # Make sure client is owner
        if chat["owner"] != client:
            return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)

        # Update chat
        chat["members"].remove(username)
        self.files.db.chats.update_one({"_id": chatid}, {"$pull": {"members": username}})

        # Send update chat event
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "update_chat",
            "payload": {
                "_id": chatid,
                "members": chat["members"]
            }
        }, "id": chat["members"]})

        # Send delete chat event to user
        self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": chatid}, "id": username})

        # Send inbox message to user
        self.supporter.createPost("inbox", username, f"You have been removed from the group chat '{chat['nickname']}' by @{client}!")

        # Send in-chat notification
        self.supporter.createPost(chatid, "Server", f"@{client} removed @{username} from the group chat.", chat_members=chat["members"])

        # Tell the client the user was removed
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def set_chat_state(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"update_chat_state:{client}"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"update_chat_state:{client}", 3, 5)

        # Check val datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check val syntax
        if ("chatid" not in val) or ("state" not in val):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract chatid and state
        chatid = val["chatid"]
        state = val["state"]

        # Check chatid and state datatypes
        if (not isinstance(chatid, str)) or (not isinstance(state, int)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check chatid syntax
        if len(chatid) < 1 or len(chatid) > 50:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Get chat
        if chatid != "livechat":
            chat = self.files.db.chats.find_one({
                "_id": chatid,
                "members": client,
                "deleted": False
            })
            if not chat:
                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
            
        # Send new state
        if chatid == "livechat":
            self.sendPacket({"cmd": "direct", "val": {
                "chatid": chatid,
                "u": client,
                "state": state
            }})
        else:
            self.sendPacket({"cmd": "direct", "val": {
                "chatid": chatid,
                "u": client,
                "state": state
            }, "id": chat["members"]})

        # Tell the client the new state was sent
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)



    # Posts

    def get_home(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get page
        page = 1
        if isinstance(val, dict):
            try:
                page = int(val.get("page"))
            except: pass

        # Get posts
        posts = self.files.db.posts.find({
            "post_origin": "home",
            "isDeleted": False
        }, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25)

        # Return posts index
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "home",
            "payload": [post["_id"] for post in posts]
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def post_home(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) < 1 or len(val) > 4000:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"post:{client}"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"post:{client}", 6, 5)

        # Check restrictions
        if self.security.is_restricted(client, Restrictions.HOME_POSTS):
            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)
        
        # Create post
        FileWrite, _ = self.supporter.createPost("home", client, val)
        if not FileWrite:
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        
        # Tell the client the post was created
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def search_user_posts(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

        # Check val datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if "query" not in val:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get query and page
        query = val["query"]
        try:
            page = int(val["page"])
        except:
            page =1

        # Check query and page datatypes
        if (not isinstance(query, str)) or (not isinstance(page, int)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get posts
        posts = self.files.db.posts.find({
            "post_origin": "home",
            "isDeleted": False,
            "u": val["query"]
        }, projection={"_id": 1}, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25)

        # Return posts index
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "user_posts",
            "index": [post["_id"] for post in posts]
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def get_inbox(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get page
        page = 1
        if isinstance(val, dict):
            try:
                page = int(val["page"])
            except: pass

        # Get posts
        posts = self.files.db.posts.find({
            "post_origin": "inbox",
            "isDeleted": False,
            "u": {"$in": [client, "Server"]}
        }, projection={"_id": 1}, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25)

        # Return posts index
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "inbox",
            "payload": [post["_id"] for post in posts]
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def get_chat_posts(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) < 1 or len(val) > 50:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Make sure chat exists
        if self.files.db.chats.count_documents({
            "_id": val,
            "members": client,
            "deleted": False
        }, limit=1) < 1:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get latest posts
        posts = self.files.db.posts.find({
            "post_origin": val,
            "isDeleted": False
        }, projection={"_id": 1}, sort=[("t.e", pymongo.DESCENDING)], limit=25)

        # Return posts index
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "chat_posts",
            "payload": [post["_id"] for post in posts]
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def post_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.ratelimited(f"post:{client}"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"post:{client}", 6, 5)

        # Check val datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check val syntax
        if ("chatid" not in val) or ("p" not in val):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract chatid and content
        chatid = val["chatid"]
        content = val["p"]

        # Check chatid and content datatypes
        if (not isinstance(chatid, str)) or (not isinstance(content, str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check chatid and content syntax
        if len(chatid) < 1 or len(chatid) > 50 or len(content) < 1 or len(content) > 4000:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Check restrictions
        if self.security.is_restricted(client, Restrictions.CHAT_POSTS):
            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)

        if chatid != "livechat":
            # Get chat
            chat = self.files.db.chats.find_one({
                "_id": chatid,
                "members": client,
                "deleted": False
            }, projection={"type": 1, "members": 1})
            if not chat:
                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
            
            # DM stuff
            if chat["type"] == 1:
                # Check privacy options
                if self.files.db.relationships.count_documents({"$or": [
                    {"_id": {"from": chat["members"][0], "to": chat["members"][1]}},
                    {"_id": {"from": chat["members"][1], "to": chat["members"][0]}}
                ], "state": 2}, limit=1) > 0:
                    return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)

                # Update user settings
                Thread(target=self.files.db.user_settings.bulk_write, args=([
                    pymongo.UpdateMany({"$or": [
                        {"_id": chat["members"][0]},
                        {"_id": chat["members"][1]}
                    ]}, {"$pull": {"active_dms": chatid}}),
                    pymongo.UpdateMany({"$or": [
                        {"_id": chat["members"][0]},
                        {"_id": chat["members"][1]}
                    ]}, {"$push": {"active_dms": {
                        "$each": [chatid],
                        "$position": 0,
                        "$slice": -150
                    }}})
                ],)).start()

        # Create post
        FileWrite, _ = self.supporter.createPost(chatid, client, content, chat_members=(chat["members"] if chatid != "livechat" else None))
        if not FileWrite:
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        
        # Tell the client the post was created
        return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def get_post(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) < 1 or len(val) > 50:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get post
        post = self.files.db.posts.find_one({"_id": post["post_origin"], "isDeleted": False})
        if not post:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check access
        if (post["post_origin"] == "inbox") and (post["u"] != client):
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        elif post["post_origin"] not in ["home", "inbox"]:
            if self.files.db.chats.count_documents({
                "_id": post["post_origin"],
                "members": client,
                "deleted": False
            }, limit=1) < 1:
                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        # Return post
        self.sendPacket({"cmd": "direct", "val": {
            "mode": "post",
            "payload": post
        }, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def delete_post(self, client, val, listener_detected, listener_id):  # TODO: needs checking
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) < 1 or len(val) > 50:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Check ratelimit
        if self.supporter.ratelimited(f"post:{client}"):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

        # Ratelimit
        self.supporter.ratelimit(f"post:{client}", 6, 5)

        # Get post
        post = self.files.db.posts.find_one({"_id": val, "isDeleted": False})
        if not post:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        # Check access
        if post["post_origin"] not in {"home", "inbox"}:
            chat = self.files.db.chats.find_one({
                "_id": post["post_origin"],
                "members": client,
                "deleted": False
            }, projection={"owner": 1, "members": 1})
            if not chat:
                return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
        if post["post_origin"] == "inbox" or post["u"] != client:
            if (post["post_origin"] in ["home", "inbox"]) or (chat["owner"] != client):
                return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)

        # Update post
        self.files.db.posts.update_one({"_id": post["_id"]}, {"$set": {
            "isDeleted": True,
            "deleted_at": int(time.time())
        }})

        # Send delete post event
        if post["post_origin"] == "home":
            self.sendPacket({"cmd": "direct", "val": {
                "mode": "delete",
                "id": post["_id"]
            }})
        else:
            self.sendPacket({"cmd": "direct", "val": {
                "mode": "delete",
                "id": post["_id"]
            }, "id": chat["members"]})

        return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)



    # Moderation/administration
    
    def report(self, client, val, listener_detected, listener_id):  # TODO: needs checking
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check val datatype
        if not isinstance(val, dict):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)

        # Check val syntax
        if ("type" not in val) or ("id" not in val):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Extract type, ID, reason, and comment
        content_type = val.get("type")
        content_id = val.get("id")
        reason = val.get("reason", "No reason specified")
        comment = val.get("comment", "")

        # Check type, ID, reason, and comment datatypes
        if (not isinstance(content_type, int)) or (not isinstance(content_id, str)) or (not isinstance(reason, str)) or (not isinstance(comment, str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Make sure the content exists
        if content_type == 0:
            post = self.files.db.posts.find_one({"_id": content_id, "post_origin": {"$ne": "inbox"}}, projection={"post_origin": 1})
            if not post:
                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
            elif post["post_origin"] != "home":
                if self.files.db.chats.count_documents({
                    "_id": post["post_origin"],
                    "members": client,
                    "deleted": False
                }, limit=1) < 1:
                    return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        elif content_type == 1:
            if self.files.db.usersv0.count_documents({"_id": content_id}, limit=1) < 1:
                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        else:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        
        # Create report
        report = self.files.db.reports.find_one({
            "content_id": content_id,
            "status": "pending",
            "type": {0: "post", 1: "user"}[content_type]
        })
        if not report:
            report = {
                "_id": str(uuid.uuid4()),
                "type": {0: "post", 1: "user"}[content_type],
                "content_id": content_id,
                "status": "pending",
                "escalated": False,
                "reports": []
            }
        for _report in report["reports"]:
            if _report["user"] == client:
                report["reports"].remove(_report)
                break
        report["reports"].append({
            "user": client,
            "ip": self.supporter.get_client_statedata(client)[0]["ip"],
            "reason": reason,
            "comment": comment,
            "time": int(time.time())
        })
        self.files.db.reports.update_one({"_id": report["_id"]}, {"$set": report}, upsert=True)

        # Tell the client the report was created
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

        # Automatically remove post and escalate report if report threshold is reached
        if content_type == 0 and report["status"] == "pending" and (not report["escalated"]):
            unique_ips = set([_report["ip"] for _report in report["reports"]])
            if len(unique_ips) >= 3:
                self.files.db.reports.update_one({"_id": report["_id"]}, {"$set": {"escalated": True}})
                self.files.db.posts.update_one({"_id": content_id, "isDeleted": False}, {"$set": {
                    "isDeleted": True,
                    "mod_deleted": True,
                    "deleted_at": int(time.time())
                }})

                """ probably not for now
                # Suspend user
                if self.security.get_ban_state(user) == "None":
                    # Construct ban obj
                    ban_obj = {
                        "state": "TempSuspension",
                        "expires": int(time.time())+21600,  # 6 hours
                        "reason": "Automatic suspension due to multiple people reporting a post made by you and/or your profile. This suspension will be automatically removed once a moderator reviews the reported content."
                    }
                    
                    # Update user
                    self.files.db.usersv0.update_one({"_id": user}, {"$set": {"ban": ban_obj}})

                    # Add log
                    self.security.add_audit_log("banned", "Server", None, {"username": user, "ban": ban_obj})

                    # Send updated ban state
                    self.sendPacket({"cmd": "direct", "val": {
                        "mode": "banned",
                        "payload": ban_obj
                    }, "id": user})
                """

import time
import uuid
import secrets
import pymongo
import os
from dotenv import load_dotenv
from copy import copy
import requests

from security import Permissions

load_dotenv()  # take environment variables from .env.

class Meower:
    def __init__(self, cl, supporter, logger, errorhandler, accounts, files):
        self.cl = cl
        self.supporter = supporter
        self.log = logger
        self.errorhandler = errorhandler
        self.accounts = accounts
        self.filesystem = files
        self.sendPacket = self.supporter.sendPacket
        result, self.supporter.filter = self.filesystem.load_item("config", "filter")
        if not result:
            self.log("Failed to load profanity filter, default will be used as fallback!")
        result, self.supporter.status = self.filesystem.load_item("config", "status")
        if not result:
            self.log("Failed to load status, server will enable repair mode!")
            self.supporter.status = {"repair_mode": True, "is_deprecated": True}
        self.log("Meower initialized!")
    
    # Some Meower-library specific utilities needed
    
    def checkForInt(self, data):
        try:
            int(data)
            return True
        except ValueError:
            return False

    def getIndex(self, location="posts", query={"post_origin": "home", "isDeleted": False}, truncate=False, page=1, sort="t.e", index_hint=None):
        if truncate:
            all_items = self.filesystem.db[location].find(query).sort(sort, pymongo.DESCENDING).hint(index_hint).skip((page-1)*25).limit(25)
        else:
            all_items = self.filesystem.db[location].find(query).hint(index_hint)
        
        item_count = self.filesystem.db[location].count_documents(query)
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

    def createPost(self, post_origin, user, content):
        post_id = str(uuid.uuid4())
        timestamp = self.supporter.timestamp(1).copy()

        post_data = {
            "type": 1,
            "post_origin": str(post_origin), 
            "u": str(user), 
            "t": timestamp, 
            "p": str(content),
            "post_id": post_id, 
            "isDeleted": False
        }
        
        filtered_content = self.supporter.wordfilter(content)
        if filtered_content != content:
            post_data["p"] = filtered_content
            post_data["unfiltered_p"] = content

        if post_origin == "home":
            result = self.filesystem.create_item("posts", post_id, post_data)

            if result:
                payload = post_data
                payload["mode"] = 1

                self.cl.sendPacket({"cmd": "direct", "val": payload})
                return True
            else:
                return False
        elif post_origin == "inbox":
            post_data["type"] = 2

            result = self.filesystem.create_item("posts", post_id, post_data)

            if result:
                payload = {
                    "mode": "inbox_message",
                    "payload": post_data
                }
                if user == "Server":
                    self.filesystem.db["usersv0"].update_many({"unread_inbox": False}, {"$set": {"unread_inbox": True}})
                    self.cl.sendPacket({"cmd": "direct", "val": payload})
                else:
                    self.filesystem.db["usersv0"].update_many({"_id": user, "unread_inbox": False}, {"$set": {"unread_inbox": True}})
                    if user in self.cl.getUsernames():
                        self.cl.sendPacket({"cmd": "direct", "val": payload, "id": user})
                return True
            else:
                return False
        elif post_origin == "livechat":
            payload = post_data
            payload["state"] = 2

            self.cl.sendPacket({"cmd": "direct", "val": payload})
            return True
        else:
            result, chat_data = self.filesystem.load_item("chats", post_origin)
            if result:
                result = self.filesystem.create_item("posts", post_id, post_data)
                if result:
                    self.filesystem.db.chats.update_one({"_id": post_origin}, {"$set": {"last_active": int(time.time())}})

                    payload = post_data
                    payload["state"] = 2

                    for member in chat_data["members"]:
                        if member in self.cl.getUsernames():
                            self.cl.sendPacket({"cmd": "direct", "val": payload, "id": member})
                    return True
                else:
                    return False
            else:
                return False
    
    def completeReport(self, _id, status):
        if status == None:
            self.filesystem.delete_item("reports", _id)
        else:
            FileRead, FileData = self.filesystem.load_item("reports", _id)
            if FileRead:
                if status == True:
                    for user in FileData["reports"]:
                        self.createPost("inbox", user, "We took action on one of your recent reports. Thank you for your help with keeping Meower a safe and welcoming place!")
                elif status == False:
                    for user in FileData["reports"]:
                        self.createPost("inbox", user, "We did not take action on one of your recent reports, the content you reported was not severe enough to warrant action being taken. We still want to thank you for your help with keeping Meower a safe and welcoming place!")
                self.filesystem.delete_item("reports", _id)

    def returnCode(self, client, code, listener_detected, listener_id):
        self.sendPacket({"cmd": "statuscode", "val": self.cl.codes[str(code)], "id": client}, listener_detected = listener_detected, listener_id = listener_id)
    
    # Networking/client utilities
    
    def ping(self, client, val, listener_detected, listener_id):
        # Returns your ping for my pong
        self.returnCode(client = client, code = "Pong", listener_detected = listener_detected, listener_id = listener_id)
    
    def get_ulist(self, client, val, listener_detected, listener_id):
        self.sendPacket({"cmd": "ulist", "val": self.cl._get_ulist(), "id": client})

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
        ip = str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"])

        # Check username and password datatypes
        if (not isinstance(username, str)) or (not isinstance(password, str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check username and password syntax
        if (len(username) > 20) or (len(password) > 255):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.check_for_spam("login", ip, burst=10, seconds=60) or self.supporter.check_for_spam("login", username, burst=10, seconds=60):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check authentication
        FileCheck, FileRead, ValidAuth, Banned = self.accounts.authenticate(username, password)
        if (not FileCheck) or (not FileRead):
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        elif not ValidAuth:
            return self.returnCode(client = client, code = "PasswordInvalid", listener_detected = listener_detected, listener_id = listener_id)
        elif Banned:
            # Get ban info
            accountData = self.filesystem.db.usersv0.find_one({"lower_username": username.lower()}, projection={"ban": 1})

            # Return info to sender
            payload = {
                "mode": "banned",
                "payload": accountData["ban"]
            }
            self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)

            # Account banned
            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)
        
        # Update netlog
        FileRead, netlog = self.filesystem.load_item("netlog", ip)
        if not FileRead:
            netlog = {
                "_id": ip,
                "users": [],
                "last_user": None,
                "last_used": None,
                "banned": False
            }
        if username not in netlog["users"]:
            if self.accounts.get_permissions(username):
                self.createPost(post_origin="inbox", user=username, content=f"Your account was logged into on a new IP address ({ip})! You are receiving this message because you have admin permissions. Please make sure to keep your account secure.")
            netlog["users"].append(username)
        netlog["last_active"] = int(time.time())
        self.filesystem.update_item("netlog", ip, netlog, upsert=True)

        # Get current tokens
        accountData = self.filesystem.db.usersv0.find_one({"lower_username": username.lower()}, projection={"tokens": 1})
        
        # Generate new token
        token = secrets.token_urlsafe(64)
        accountData["tokens"].append(token)
        self.accounts.update_setting(username, {"tokens": accountData["tokens"], "last_ip": ip}, forceUpdate=True)
        
        # Set client authenticated state
        self.supporter.autoID(client, username) # Give the client an AutoID
        self.supporter.setAuthenticatedState(client, True) # Make the server know that the client is authed
        
        # Return info to sender
        payload = {
            "mode": "auth",
            "payload": {
                "username": username,
                "token": token
            }
        }
        self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        
        # Tell the client it is authenticated
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
    
    def gen_account(self, client, val, listener_detected, listener_id):
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
        ip = str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"])

        # Check username and password datatypes
        if (not isinstance(username, str)) or (not isinstance(password, str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check username and password syntax
        if (len(username) > 20) or (len(password) > 255):
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check ratelimit
        if self.supporter.check_for_spam("signup", ip, burst=3, seconds=60):
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check if IP is VPN
        iphub_key = os.getenv("IPHUB_KEY")
        if iphub_key:
            if ip in self.supporter.known_vpns:
                return self.returnCode(client = client, code = "Blocked", listener_detected = listener_detected, listener_id = listener_id)
            elif ip not in self.supporter.good_ips:
                ip_info = requests.get(f"http://v2.api.iphub.info/ip/{ip}", headers={"X-Key": iphub_key})
                if ip_info.status_code == 200:
                    if ip_info.json()["block"] == 1:
                        self.log(f"{ip} was detected as a VPN/proxy")
                        self.supporter.known_vpns.add(ip)
                        return self.returnCode(client = client, code = "Blocked", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        self.supporter.good_ips.add(ip)
                else:
                    self.log(f"{ip} was detected using an invalid IP")
                    return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)

        # Create account
        FileCheck, FileWrite = self.accounts.create_account(username, password)
        if (not FileCheck) or (not FileWrite):
            return self.returnCode(client = client, code = "IDExists", listener_detected = listener_detected, listener_id = listener_id)
        
        # Send welcome message
        self.createPost(post_origin="inbox", user=username, content="Welcome to Meower! We welcome you with open arms! You can get started by making friends in the global chat or home, or by searching for people and adding them to a group chat. We hope you have fun!")

        # Update netlog
        FileRead, netlog = self.filesystem.load_item("netlog", ip)
        if not FileRead:
            netlog = {
                "_id": ip,
                "users": [],
                "last_user": None,
                "last_used": None,
                "banned": False
            }
        if username not in netlog["users"]:
            if self.accounts.get_permissions(username):
                self.createPost(post_origin="inbox", user=username, content=f"Your account was logged into on a new IP address ({ip})! You are receiving this message because you have admin permissions. Please make sure to keep your account secure.")
            netlog["users"].append(username)
        netlog["last_active"] = int(time.time())
        self.filesystem.update_item("netlog", ip, netlog, upsert=True)

        # Generate new token
        token = secrets.token_urlsafe(64)
        self.accounts.update_setting(username, {"tokens": [token], "last_ip": ip}, forceUpdate=True)
        
        # Set client authenticated state
        self.supporter.autoID(client, username) # Give the client an AutoID
        self.supporter.setAuthenticatedState(client, True) # Make the server know that the client is authed
        
        # Return info to sender
        payload = {
            "mode": "auth",
            "payload": {
                "username": username,
                "token": token
            }
        }
        self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        
        # Tell the client it is authenticated
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def get_profile(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                FileCheck, FileRead, Payload = self.accounts.get_account(val, (val != client), True)
                
                if FileCheck and FileRead:
                    payload = {
                        "mode": "profile",
                        "payload": Payload,
                        "user_id": val
                    }
                    
                    self.log("{0} fetching profile {1}".format(client, val))
                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                    
                    # Return to the client it's data
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def update_config(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                self.log("{0} updating config".format(client))

                if "quote" in val:
                    if self.accounts.get_ban_state(client) in {"TempSuspension", "PermSuspension"}:
                        del val["quote"]

                FileCheck, FileRead, FileWrite = self.accounts.update_setting(client, val)
                if FileCheck and FileRead and FileWrite:
                    # Sync states between multiple sessions
                    payload = {
                        "mode": "update_config",
                        "payload": val
                    }
                    self.sendPacket({"cmd": "direct", "val": payload, "id": client})

                    # OK
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    # General
    
    def get_home(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if (type(val) == dict) and ("page" in val) and self.checkForInt(val["page"]):
                page = int(val["page"])
            else:
                page = 1
            home_index = self.getIndex("posts", {"post_origin": "home", "isDeleted": False}, truncate=True, page=page)
            for i in range(len(home_index["index"])):
                home_index["index"][i] = home_index["index"][i]["_id"]
            payload = {
                "mode": "home",
                "payload": home_index
            }
            self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def post_home(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 4000:
                    if not self.supporter.check_for_spam("posts", client, burst=10, seconds=5):
                        # Check ban state
                        if self.accounts.get_ban_state(client) in {"TempSuspension", "PermSuspension"}:
                            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)

                        # Create post
                        result = self.createPost(post_origin="home", user=client, content=val)
                        if result:
                            self.log("{0} posting home message".format(client))
                            # Tell client message was sent
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            self.supporter.ratelimit(client)
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
    
    def get_post(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                result, payload = self.filesystem.load_item("posts", val)
                if result:
                    FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
                    if FileCheck and FileRead:
                        hasPermission = False
                        if self.accounts.has_permission(accountData["permissions"], Permissions.DELETE_POSTS):
                            hasPermission = True
                        else:
                            if payload["post_origin"] == "home":
                                hasPermission = True
                            elif (payload["post_origin"] == "inbox") and ((payload["u"] == client) or (payload["u"] == "Server")):
                                hasPermission = True
                            else:
                                result, chatdata = self.filesystem.load_item("chats", payload["post_origin"])
                                if result:
                                    if (not chatdata["deleted"]) and (client in chatdata["members"]):
                                        hasPermission = True
                        if hasPermission:
                            if payload["isDeleted"] and self.accounts.has_permission(accountData["permissions"], Permissions.DELETE_POSTS):
                                # Post is deleted
                                self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                payload = {
                                    "mode": "post",
                                    "payload": payload
                                }

                            self.log("{0} getting post {1}".format(client, val))

                            # Relay post to client
                            self.sendPacket({"cmd": "direct", "val": payload, "id": client})
                            
                            # Tell client message was sent
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Client doesn't have access to post
                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        if ((not FileCheck) and FileRead):
                            # Post not found
                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    # Logging and data management
    
    def search_user_posts(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if ("query" in val) and (type(val["query"]) == str):
                    if ("page" in val) and self.checkForInt(val["page"]):
                        page = int(val["page"])
                    else:
                        page = 1

                    post_index = self.getIndex(location="posts", query={"u": val["query"], "post_origin": "home", "isDeleted": False}, truncate=True, page=page, index_hint="user_search")
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

    def close_report(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.DELETE_POSTS) or self.accounts.has_permission(accountData["permissions"], Permissions.CLEAR_USER_QUOTES) or self.accounts.has_permission(accountData["permissions"], Permissions.SEND_ALERTS) or self.accounts.has_permission(accountData["permissions"], Permissions.EDIT_BAN_STATES):
                    if type(val) == str:
                        self.completeReport(val, False)
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def clear_home(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.DELETE_POSTS):
                    if (type(val) == dict) and ("page" in val) and self.checkForInt(val["page"]):
                        page = int(val["page"])
                    else:
                        page = 1
                    home_index = self.getIndex("posts", {"post_origin": "home", "isDeleted": False}, truncate=True, page=page)
                    for post in home_index["index"]:
                        post["isDeleted"] = True
                        self.filesystem.write_item("posts", post["_id"], post)
                        self.completeReport(val, None)
                    
                    # Return to the client it's data
                    self.sendPacket({"cmd": "direct", "val": "", "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

                    # Log action
                    logging_chat = os.getenv("MOD_LOGGING_CHAT")
                    if logging_chat:
                        self.createPost(post_origin=logging_chat, user="Server", content=f"@{client} cleared all posts on home page #{page}")
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def clear_user_posts(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
                if FileCheck and FileRead:
                    if self.accounts.has_permission(accountData["permissions"], Permissions.CLEAR_USER_POSTS):
                        # Delete all posts
                        query = {"u": val, "post_origin": "home", "isDeleted": False}
                        posts = list(self.filesystem.db.posts.find(query, projection={"_id": 1}).hint("user_search"))
                        self.filesystem.db.posts.update_many(query, {"$set": {"isDeleted": True, "mod_deleted": True, "deleted_at": int(time.time())}}).hint("user_search")

                        # Complete reports and announce post deletion
                        for post in posts:
                            self.completeReport(post["_id"], True)
                            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": post["_id"]}})

                        # Give user report feedback
                        self.completeReport(val, True)
                        
                        # Tell the client it deleted all posts
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

                        # Log action
                        logging_chat = os.getenv("MOD_LOGGING_CHAT")
                        if logging_chat:
                            self.createPost(post_origin=logging_chat, user="Server", content=f"@{client} cleared all of @{val}'s posts")
                    else:
                        self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
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

    def alert(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.SEND_ALERTS):
                    if type(val) == dict:
                        if ("username" in val) and ("p" in val):
                            if (type(val["username"]) == str) and (type(val["p"]) == str):
                                if self.accounts.account_exists(val["username"]):
                                    
                                    self.completeReport(val["username"], True)
                                    
                                    # Give report feedback
                                    self.completeReport(val, True)
                                    
                                    # Send alert
                                    self.createPost(post_origin="inbox", user=val["username"], content="Message from a moderator: {0}".format(val["p"]))

                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

                                    # Log action
                                    logging_chat = os.getenv("MOD_LOGGING_CHAT")
                                    if logging_chat:
                                        self.createPost(post_origin=logging_chat, user="Server", content=f"@{client} sent an alert to @{val['username']}: {val['p']}")
                                else:
                                    # Account not found
                                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def announce(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.SEND_ANNOUNCEMENTS):
                    if type(val) == str:
                        self.createPost(post_origin="inbox", user="Server", content=val)
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

                        # Log action
                        logging_chat = os.getenv("MOD_LOGGING_CHAT")
                        if logging_chat:
                            self.createPost(post_origin=logging_chat, user="Server", content=f"@{client} made an announcement: {val}")
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def block(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.BLOCK_IPS):
                    if type(val) == str:
                        # Get netlog
                        FileRead, netlog = self.filesystem.load_item("netlog", val)
                        if not FileRead:
                            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                        
                        # Block IP address
                        self.log("Blocking IP address {0}".format(val))
                        self.filesystem.update_item("netlog", val, {"banned": True})
                        self.cl.blockIP(val)

                        # Kick all clients on the netlog
                        FileRead, netlog = self.filesystem.load_item("netlog", val)
                        if FileRead:
                            for username in netlog["users"]:
                                client = self.cl._get_obj_of_username(username)
                                if netlog["_id"] in self.cl._get_ip_of_obj(client):
                                    self.supporter.kickUser(username, "Blocked")

                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def unblock(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.BLOCK_IPS):
                    if type(val) == str:
                        # Unblock IP address
                        self.log("Unblocking IP address {0}".format(val))
                        FileWrite = self.filesystem.update_item("netlog", val, {"banned": False})
                        if FileWrite:
                            self.cl.unblockIP(val)
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def kick_all(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.SYSADMIN):
                    # Kick all online users
                    self.log("Kicking all clients")

                    for client in self.cl.wss.clients:
                        self.cl.kickClient(client)
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def force_kick(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.KICK_USERS):
                    # Forcibly kill all locked out/bugged sessions under that username - This is for extreme cases of account lockup only!
                    if not self.cl._get_obj_of_username(val):

                        # if the username is stuck in memory, delete it
                        if val in self.cl.statedata["ulist"]["usernames"]: 
                            del self.cl.statedata["ulist"]["usernames"][val]
                            self.cl._send_to_all({"cmd": "ulist", "val": self.cl._get_ulist()})
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                        return
                    
                    # Why do I hear boss music?
                    for session in self.cl._get_obj_of_username(val):
                        self.log("Forcing killing session {0}".format(session['id']))
                        try:
                           # Attempt to disconnect session - Most of the time this will result in a broken pipe error
                            self.cl.kickClient(session)
                        
                        except Exception as e:
                            self.log("Session {0} force kill exception: {1} (If this is a BrokenPipe error, this is expected to occur)".format(session['id'], e))

                        try:
                            # If it is a broken pipe, forcibly free the session from memory
                            self.cl._closed_connection_server(session, self.cl)
                        except Exception as e:
                            self.log("Session {0} force kill exception: {1}".format(session['id'], e))
                    
                    # Return status to the client
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def kick(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.KICK_USERS):
                    if type(val) == str:
                        if val in self.cl.getUsernames():
                            # Revoke sessions
                            FileCheck, FileRead, FileWrite = self.accounts.update_setting(val, {"tokens": []}, forceUpdate=True)
                            if FileCheck and FileRead and FileWrite:

                                # Kick the user
                                self.supporter.kickUser(val)
                                
                                # Tell client it kicked the user
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

                                # Log action
                                logging_chat = os.getenv("MOD_LOGGING_CHAT")
                                if logging_chat:
                                    self.createPost(post_origin=logging_chat, user="Server", content=f"@{client} kicked @{val}")
                            else:
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # User not found
                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def get_ip_data(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.VIEW_IPS):
                    if type(val) == str:
                        if self.filesystem.does_item_exist("netlog", str(val)):
                            result, netdata = self.filesystem.load_item("netlog", str(val))
                            if result:
                                netdata["ip"] = str(val)
                                payload = {
                                    "mode": "ip_data",
                                    "payload": netdata
                                }
                                self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Some other error, raise an internal error.
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # IP not found
                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def ban(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

        # Check client level
        FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
        if not (FileCheck and FileRead):
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        elif not self.accounts.has_permission(accountData["permissions"], Permissions.EDIT_BAN_STATES):
            return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if (not isinstance(val, dict)) or (not isinstance(val.get("username"), str)) or (not isinstance(val.get("state"), str)) or (not isinstance(val.get("expires"), int)) or (not isinstance(val.get("reason"), str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Construct ban object
        ban_obj = {
            "state": val["state"],
            "expires": val["expires"],
            "reason": val["reason"]
        }

        # Update user
        FileCheck, FileRead, FileWrite = self.accounts.update_setting(val["username"], {"ban": ban_obj}, forceUpdate=True)
        if not (FileCheck and FileRead):
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        elif not FileWrite:
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)

        # Kick client or send updated ban status
        if val["state"] in {"TempBan", "PermBan"}:
            if (val["state"] == "PermBan") or (val["expires"] > time.time()):
                self.supporter.kickUser(val["username"], status="Banned")
        else:
            payload = {
                "mode": "banned",
                "payload": ban_obj
            }
            self.sendPacket({"cmd": "direct", "val": payload, "id": val["username"]}, listener_detected = listener_detected, listener_id = listener_id)

        # Give report feedback
        self.completeReport(val, True)

        # Log action
        logging_chat = os.getenv("MOD_LOGGING_CHAT")
        if logging_chat:
            self.createPost(post_origin=logging_chat, user="Server", content=f"@{client} updated @{val}'s ban status\n\nState: {val['state']}\nExpires: {val['expires']}\nReason: {val['reason']}")

        # Tell client it banned the user
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def repair_mode(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if self.accounts.has_permission(accountData["permissions"], Permissions.SYSADMIN):
                    self.log("Enabling repair mode")

                    # Enable repair mode
                    self.supporter.status["repair_mode"] = True
                    FileWrite = self.filesystem.update_item("config", "status", {"repair_mode": True})
                    if not FileWrite:
                        return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)

                    # Tell client it enabled repair mode
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

                    # Log action
                    logging_chat = os.getenv("MOD_LOGGING_CHAT")
                    if logging_chat:
                        self.createPost(post_origin=logging_chat, user="Server", content=f"@{client} enabled repair mode")

                    time.sleep(1)

                    # Kick all online users
                    self.log("Kicking all clients")
                    for client in copy(self.cl.wss.clients):
                        self.cl.kickClient(client)
                else:
                    self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
            else:
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    # Chat-related
    
    def delete_post(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) > 50:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

        # Get post
        FileRead, postdata = self.filesystem.load_item("posts", val)
        if (not FileRead) or postdata["isDeleted"]:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        # Self-delete
        if postdata["post_origin"] != "inbox":
            if (postdata["u"] == client) or ((postdata["u"] == "Discord") and postdata["p"].startswith(f"{client}:")):
                self.filesystem.update_item("posts", val, {"isDeleted": True, "deleted_at": int(time.time())})
                self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}})
                return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

        # Chat owner delete
        if postdata["post_origin"] != "home":
            FileRead, chatdata = self.filesystem.load_item("chats", postdata["post_origin"])
            if (not FileRead) or chatdata["deleted"]:
                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

            if client == chatdata["owner"]:
                self.filesystem.update_item("posts", val, {"isDeleted": True, "deleted_at": int(time.time())})
                self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}})
                return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

        # Admin delete
        if self.accounts.has_permission(self.accounts.get_permissions(client), Permissions.DELETE_POSTS):
            if postdata["post_origin"] != "inbox":
                self.createPost(post_origin="inbox", user=postdata["u"], content="One of your posts were removed by a moderator because it violated the Meower terms of service! If you think this is a mistake, please report this message and we will look further into it. Post: '{0}'".format(postdata["p"]))
            self.filesystem.update_item("posts", val, {"isDeleted": True, "mod_deleted": True, "deleted_at": int(time.time())})
            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}})
            return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        
        return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
    
    def create_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 32:
                    # Check ban state
                    if self.accounts.get_ban_state(client) in {"TempRestriction", "PermRestriction", "TempSuspension", "PermSuspension"}:
                        return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)

                    val = self.supporter.wordfilter(val)
                    result = self.filesystem.create_item("chats", str(uuid.uuid4()), {
                        "nickname": val,
                        "owner": client,
                        "members": [client],
                        "created": int(time.time()),
                        "last_active": int(time.time()),
                        "deleted": False
                    })
                    if result:
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def leave_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 50:
                    if self.filesystem.does_item_exist("chats", val):
                        result, chatdata = self.filesystem.load_item("chats", val)
                        if result:
                            if (not chatdata["deleted"]) and (client in chatdata["members"]):
                                # Remove member
                                chatdata["members"].remove(client)

                                # Delete chat, if empty
                                if len(chatdata["members"]) < 1:
                                    self.filesystem.delete_item("chats", chatdata["_id"])
                                    self.filesystem.db.posts.delete_many({"post_origin": chatdata["_id"], "isDeleted": False})
                                else:
                                    # Transfer ownership, if owner
                                    if client == chatdata["owner"]:
                                        chatdata["owner"] = chatdata["members"][0]

                                    # Update chat
                                    self.filesystem.update_item("chats", chatdata["_id"], {
                                        "owner": chatdata["owner"],
                                        "members": chatdata["members"]
                                    })

                                    # Send update event
                                    payload = {
                                        "mode": "update_chat",
                                        "payload": chatdata
                                    }
                                    for username in chatdata["members"]:
                                        if username in self.cl.getUsernames():
                                            self.sendPacket({"cmd": "direct", "val": payload, "id": username})

                                    # Send in-chat notification
                                    self.createPost(chatdata["_id"], "Server", f"@{client} has left the group chat.")

                                # Tell the client it left the chat
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

                                # Send delete event
                                self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": chatdata["_id"]}, "id": client})
                            else:
                                self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
            chat_index = self.getIndex(location="chats", query={"members": {"$all": [client]}, "deleted": False}, truncate=True, page=page, sort="last_active")
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
                            if (not chatdata["deleted"]) and (client in chatdata["members"]):
                                payload = {
                                    "mode": "chat_data",
                                    "payload": {
                                        "_id": chatdata["_id"],
                                        "chatid": chatdata["_id"],
                                        "nickname": chatdata["nickname"],
                                        "owner": chatdata["owner"],
                                        "members": chatdata["members"],
                                        "created": chatdata["created"],
                                        "last_active": chatdata["last_active"]
                                    }
                                }
                                self.sendPacket({"cmd": "direct", "val": payload, "id": client})
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # User isn't in chat
                                self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def update_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if (not isinstance(val, dict)) or (not isinstance(val.get("chatid"), str)):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)

        # Get updated values
        updated_values = {}
        if "nickname" in val:
            if not isinstance(val["nickname"], str):
                return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
            
            if len(val["nickname"]) > 32:
                return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)

            updated_values["nickname"] = val["nickname"]
        elif "owner" in val:
            if not isinstance(val["owner"], str):
                return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
            
            if val["owner"] not in chatdata["members"]:
                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

            updated_values["owner"] = val["owner"]
        elif "deleted" in val:
            if not isinstance(val["deleted"], bool):
                return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
            
            updated_values["deleted"] = val["deleted"]

        # Check ban state
        if self.accounts.get_ban_state(client) in {"TempSuspension", "PermSuspension"}:
            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get chat
        file_read, chatdata = self.filesystem.load_item("chats", val["chatid"])
        if not file_read:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        # Check permissions
        if (chatdata["deleted"] or (client != chatdata["owner"])) and (not self.accounts.has_permission(self.accounts.get_permissions(client), Permissions.EDIT_CHATS)):
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        # Update chat
        updated_values["last_active"] = int(time.time())
        file_write = self.filesystem.update_item("chats", chatdata["_id"], updated_values)
        if not file_write:
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        chatdata.update(updated_values)

        # Send update chat event
        payload = {
            "mode": "update_chat",
            "payload": chatdata
        }
        for username in chatdata["members"]:
            if username in self.cl.getUsernames():
                self.sendPacket({"cmd": "direct", "val": payload, "id": username})

        # Send in-chat notifications
        if "nickname" in val:
            self.createPost(chatdata["_id"], "Server", f"@{client} changed the name of the group chat to @{val['nickname']}.")
        if "owner" in val:
            self.createPost(chatdata["_id"], "Server", f"@{client} transferred ownership of the group chat to @{val['owner']}.")

        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def get_chat_posts(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 50:
                    if self.filesystem.does_item_exist("chats", val):
                        result, chatdata = self.filesystem.load_item("chats", val)
                        if result:
                            if (not chatdata["deleted"]) and (client in chatdata["members"]):
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
                                # User isn't in chat
                                self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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

    def set_chat_state(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):  # Not authenticated
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        elif not ((type(val) == dict) and (("state" in val) and self.checkForInt(val["state"]) and (("chatid" in val) and (type(val["chatid"]) == str)))):  # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
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
            if chatdata["deleted"] or (client not in chatdata["members"]):
                # User not in chat
                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

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
                if (not len(post) > 2000) and (not len(chatid) > 50):
                    if not self.supporter.check_for_spam("posts", client, burst=10, seconds=5):
                        # Check ban state
                        if self.accounts.get_ban_state(client) in {"TempSuspension", "PermSuspension"}:
                            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)

                        if chatid == "livechat":
                            result = self.createPost(post_origin=chatid, user=client, content=post)
                            if result:
                                self.filesystem.db["chats"].update_one({"_id": chatid}, {"$set": {"last_active": int(time.time())}})
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                self.supporter.ratelimit(client)
                            else:
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            result, chat_data = self.filesystem.load_item("chats", chatid)
                            if result:
                                if (not chat_data["deleted"]) and (client in chat_data["members"]):
                                    result = self.createPost(post_origin=chatid, user=client, content=post)
                                    if result:
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                        self.supporter.ratelimit(client)
                                    else:
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
                    
                    if not self.supporter.check_for_spam("update_chat", client, burst=10, seconds=3):
                        # Read chat UUID's nickname
                        FileRead, chatdata = self.filesystem.load_item("chats", chatid)
                        if FileRead:
                            if (not chatdata["deleted"]) and (client in chatdata["members"]):
                                # Check if the group chat is full
                                if len(chatdata["members"]) < 256:
                                    # Check ban state
                                    if self.accounts.get_ban_state(client) in {"TempRestriction", "PermRestriction", "TempSuspension", "PermSuspension"}:
                                        return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)

                                    # Check if the user exists
                                    if self.filesystem.does_item_exist("usersv0", username):
                                        # Add user to group chat
                                        if (username not in chatdata["members"]) and (username != "Server"):
                                            chatdata["members"].append(username)
                                            FileWrite = self.filesystem.write_item("chats", chatid, chatdata)

                                            if FileWrite:
                                                # Inbox message to say the user was added to the group chat
                                                self.createPost("inbox", username, "You have been added to the group chat '{0}' by @{1}!".format(chatdata["nickname"], client))

                                                # Chat message to say the user was added to the group chat
                                                self.createPost(chatid, "Server", "@{0} added @{1} to the group chat.".format(client, username))

                                                # Tell client user was added
                                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                            else:
                                                # Some other error, raise an internal error.
                                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                        else:
                                            self.returnCode(client = client, code = "IDExists", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "ChatFull", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Rate limiter
                        self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
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
                    
                    if not self.supporter.check_for_spam("update_chat", client, burst=10, seconds=3):
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

                                        # Chat message to say the user was removed from the group chat
                                        self.createPost(chatid, "Server", "@{0} removed @{1} from the group chat.".format(client, username))

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
                        # Rate limiter
                        self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
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
                
                inbox_index = self.getIndex(location="posts", query={"post_origin": "inbox", "isDeleted": False, "u": {"$in": [client, "Server"]}}, page=page)
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

    def change_pswd(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if ("old" in val) and ("new" in val):
                    if (type(val["old"]) == str) and (type(val["new"]) == str):
                        old_password = val["old"]
                        new_password = val["new"]
                        if not self.supporter.check_for_spam("password-change", client, burst=1, seconds=60):         
                            if (len(old_password) <= 255) and (len(new_password) <= 255):
                                # Check old password
                                FileCheck, FileRead, ValidAuth, _ = self.accounts.authenticate(client, old_password)
                                if FileCheck and FileRead:
                                    if ValidAuth:
                                        # Change password
                                        FileCheck, FileRead, FileWrite = self.accounts.change_password(client, new_password)
                                        if FileCheck and FileRead and FileWrite:
                                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                        else:
                                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        self.returnCode(client = client, code = "PasswordInvalid", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Ratelimited
                            self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
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

    def del_tokens(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, FileWrite = self.accounts.update_setting(client, {"tokens": []}, forceUpdate=True)
            if FileCheck and FileRead and FileWrite:
                # Disconnect the user
                try:
                    self.supporter.kickUser(client, "LoggedOut")
                except:
                    self.cl._closed_connection_server(client, self.cl)
            else:
                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def del_account(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if not self.supporter.isAuthenticated(client):
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check datatype
        if not isinstance(val, str):
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Check syntax
        if len(val) > 255:
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        
        # Get user to delete
        if self.accounts.has_permission(self.accounts.get_permissions(client), Permissions.DELETE_USERS):
            username = val
        else:
            if self.accounts.get_ban_state(client) in {"TempRestriction", "PermRestriction", "TempSuspension", "PermSuspension"}:
                return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)

            if not self.supporter.check_for_spam("login", client, burst=10, seconds=60):
                return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)

            username = client

        # Delete user
        fileread = self.filesystem.delete_item("usersv0", username)
        if not fileread:
            return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)

        # Give user report feedback
        self.completeReport(username, None)

        # Update netlog
        self.filesystem.db.netlog.update_many({"users": {"$all": [username]}}, {"$pull": {"users": username}})

        # Update chats
        self.filesystem.db.chats.update_many({"members": {"$all": [username]}}, {"$pull": {"members": username}})

        # Delete posts
        query = {"u": username}
        post_ids = self.filesystem.find_items("posts", query)
        self.filesystem.db.posts.delete_many(query)

        # Complete reports and announce post deletion
        for post_id in post_ids:
            self.completeReport(post_id, None)
            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": post_id}})

        # Tell the client the user was deleted
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

        # Kick user
        time.sleep(1)
        try:
            self.supporter.kickUser(username, "LoggedOut")
        except:
            self.cl._closed_connection_server(username, self.cl)

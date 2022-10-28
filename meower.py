import time
import uuid
import secrets
import pymongo
import os
from dotenv import load_dotenv
import requests

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
            self.supporter.status = {"repair_mode": True, "is_deprecated": False}
        self.log("Meower initialized!")
    
    # Some Meower-library specific utilities needed
    
    def checkForInt(self, data):
        try:
            int(data)
            return True
        except ValueError:
            return False

    def getIndex(self, location="posts", query={"post_origin": "home", "isDeleted": False},  truncate=False, page=1, sort="t.e"):
        if truncate:
            all_items = self.filesystem.db[location].find(query).sort("t.e", pymongo.DESCENDING).skip((page-1)*25).limit(25)
        else:
            all_items = self.filesystem.db[location].find(query)
        
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

            result = self.filesystem.create_item("posts", post_id, post_data)

            if result:
                payload = post_data
                payload["mode"] = 1

                self.cl.sendPacket({"cmd": "direct", "val": payload})
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

            result = self.filesystem.create_item("posts", post_id, post_data)

            if result:
                payload = {
                    "mode": "inbox_message",
                    "payload": {}
                }
                if user == "Server":
                    self.filesystem.db["usersv0"].update_many({"unread_inbox": False}, {"$set": {"unread_inbox": True}})
                    self.cl.sendPacket({"cmd": "direct", "val": payload})
                elif user in self.cl.getUsernames():
                    self.filesystem.db["usersv0"].update_many({"_id": user, "unread_inbox": False}, {"$set": {"unread_inbox": True}})
                    self.cl.sendPacket({"cmd": "direct", "val": payload, "id": user})
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

            self.cl.sendPacket({"cmd": "direct", "val": payload})
            return True
        else:
            result, chat_data = self.filesystem.load_item("chats", post_origin)
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

                result = self.filesystem.create_item("posts", post_id, post_data)

                if result:
                    # Remove code below once client is updated
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
                        self.createPost("inbox", user, "Sadly, we could not take action on one of your recent reports. The content you reported was not severe enough to warrant action being taken. We still want to thank you for your help with keeping Meower a safe and welcoming place!")
                self.filesystem.delete_item("reports", _id)

    def returnCode(self, client, code, listener_detected, listener_id):
        self.sendPacket({"cmd": "statuscode", "val": self.cl.codes[str(code)], "id": client}, listener_detected = listener_detected, listener_id = listener_id)
    
    # Networking/client utilities
    
    def ping(self, client, val, listener_detected, listener_id):
        # Returns your ping for my pong
        self.returnCode(client = client, code = "Pong", listener_detected = listener_detected, listener_id = listener_id)
    
    def version_chk(self, client, val, listener_detected, listener_id):
        if type(val) == str:
            # Load the supported versions list
            result, payload = self.filesystem.load_item("config", "supported_versions")
            if result:
                if val in payload["index"]:
                    # If the client version string exists in the list, it is supported
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Either unsupported or out of date
                    self.returnCode(client = client, code = "ObsoleteClient", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Bad datatype
            self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
    
    def get_ulist(self, client, val, listener_detected, listener_id):
        self.sendPacket({"cmd": "ulist", "val": self.cl._get_ulist(), "id": client})

    # Accounts and security
    
    def authpswd(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if not self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if ("username" in val) and ("pswd" in val):
                    
                    # Extract username and password for simplicity
                    username = val["username"]
                    password = val["pswd"]
                    ip = str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"])
                    
                    if ((type(username) == str) and (type(password) == str)):
                        if not self.supporter.checkForBadCharsUsername(username):
                            if not self.supporter.checkForBadCharsPost(password):
                                if not (self.supporter.check_for_spam("login", ip, burst=5, seconds=60)) or (self.supporter.check_for_spam("login", username, burst=5, seconds=60)):
                                    FileCheck, FileRead, ValidAuth, Banned = self.accounts.authenticate(username, password)
                                    if FileCheck and FileRead:
                                        if ValidAuth:
                                            self.supporter.kickUser(username, status="IDConflict") # Kick bad clients missusing the username
                                            self.filesystem.create_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), {"users": [], "last_user": username})
                                            status, netlog = self.filesystem.load_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]))
                                            if status:
                                                if not username in netlog["users"]:
                                                    netlog["users"].append(username)
                                                netlog["last_user"] = username
                                                self.filesystem.write_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), netlog)
                                                FileCheck, FileRead, accountData = self.accounts.get_account(username, False, False)
                                                token = secrets.token_urlsafe(64)
                                                accountData["tokens"].append(token)
                                                self.accounts.update_setting(username, {"last_ip": str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), "tokens": accountData["tokens"]}, forceUpdate=True)
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
                                                
                                                # Log peak users
                                                self.supporter.log_peak_users()
                                            else:
                                                self.returnCode(client = client, code = "Internal", listener_detected = listener_detected, listener_id = listener_id)
                                        else:
                                            if Banned:
                                                # Account banned
                                                self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)
                                            else:
                                                # Password invalid
                                                self.returnCode(client = client, code = "PasswordInvalid", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        if ((not FileCheck) and FileRead):
                                            # Account does not exist
                                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                                        else:
                                            # Some other error, raise an internal error.
                                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Ratelimited
                                    self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Bad characters being used
                                self.returnCode(client = client, code = "IllegalChars", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Bad characters being used
                            self.returnCode(client = client, code = "IllegalChars", listener_detected = listener_detected, listener_id = listener_id)
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
            # Already authenticated
            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
    
    def gen_account(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if not self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if ("username" in val) and ("pswd" in val):
                    
                    # Extract username and password for simplicity
                    username = val["username"]
                    password = val["pswd"]
                    ip = str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"])
                    
                    if ((type(username) == str) and (type(password) == str)):
                        if not (len(username) > 20) or (password > 74):
                            if not self.supporter.checkForBadCharsUsername(username):
                                # Check if the IP is a VPN/proxy
                                if ip in self.supporter.known_vpns:
                                    return self.returnCode(client = client, code = "Blocked", listener_detected = listener_detected, listener_id = listener_id)
                                elif ip not in self.supporter.good_ips:
                                    iphub_key = os.getenv("IPHUB_KEY")
                                    if iphub_key != "":
                                        ip_info = requests.get("http://v2.api.iphub.info/ip/{0}".format(ip), headers={"X-Key": iphub_key})
                                        if ip_info.status_code == 200:
                                            if ip_info.json()["block"] == 1:
                                                self.log("{0} was detected as a VPN/proxy".format(ip))
                                                self.supporter.known_vpns.append(ip)
                                                return self.returnCode(client = client, code = "Blocked", listener_detected = listener_detected, listener_id = listener_id)
                                            else:
                                                self.supporter.good_ips.append(ip)
                                        else:
                                            self.log("{0} was detected using an invalid IP")
                                            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        self.log("No IPHub API key detected, skipping VPN/proxy check for {0}".format(ip))

                                if not self.supporter.check_for_spam("signup", ip, burst=2, seconds=120):
                                    FileCheck, FileWrite = self.accounts.create_account(username, password)
                                    
                                    if FileCheck and FileWrite:
                                        self.filesystem.create_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), {"users": [], "last_user": username})
                                        status, netlog = self.filesystem.load_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]))
                                        if status:
                                            if not username in netlog["users"]:
                                                netlog["users"].append(username)
                                            netlog["last_user"] = username
                                            self.filesystem.write_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), netlog)
                                            FileCheck, FileRead, accountData = self.accounts.get_account(username, False, False)
                                            token = secrets.token_urlsafe(64)
                                            accountData["tokens"].append(token)
                                            self.accounts.update_setting(username, {"last_ip": str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), "tokens": accountData["tokens"]}, forceUpdate=True)
                                            self.supporter.autoID(client, username) # If the client is JS-based then give them an AutoID
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
                                            
                                            # Log peak users
                                            self.supporter.log_peak_users()

                                            # Send welcome message
                                            self.createPost(post_origin="inbox", user=username, content="Welcome to Meower! We welcome you with open arms! You can get started by making friends in the global chat or home, or by searching for people and adding them to a group chat. We hope you have fun!")
                                        else:
                                            self.returnCode(client = client, code = "Internal", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        if ((not FileCheck) and FileWrite):
                                            # Account already exists
                                            self.returnCode(client = client, code = "IDExists", listener_detected = listener_detected, listener_id = listener_id)
                                        else:
                                            # Some other error, raise an internal error.
                                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Ratelimited
                                    self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Bad characters being used
                                self.returnCode(client = client, code = "IllegalChars", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Message too large
                            self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
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
            # Already authenticated
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
                if not len(val) > 360:
                    if not self.supporter.check_for_spam("posts", client, burst=6, seconds=5):
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
                        if accountData["lvl"] >= 1:
                            hasPermission = True
                        else:
                            if payload["post_origin"] == "home":
                                hasPermission = True
                            elif (payload["post_origin"] == "inbox") and ((payload["u"] == client) or (payload["u"] == "Server")):
                                hasPermission = True
                            else:
                                result, chatdata = self.filesystem.load_item("chats", payload["post_origin"])
                                if result:
                                    if client in chatdata["members"]:
                                        hasPermission = True
                        if hasPermission:
                                if payload["isDeleted"] and accountData["lvl"] < 1:
                                    payload = {
                                        "mode": "post",
                                        "payload": {
                                            "isDeleted": True
                                        }
                                    }
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
                            self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        if ((not FileCheck) and FileRead):
                            # Account not found
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

    def close_report(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 1:
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
                if accountData["lvl"] >= 1:
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
                    if accountData["lvl"] >= 1:
                        # Delete all posts
                        post_index = self.getIndex("posts", {"post_origin": "home", "u": str(val), "isDeleted": False}, truncate=False)
                        for post in post_index["index"]:
                            post["isDeleted"] = True
                            self.filesystem.write_item("posts", post["_id"], post)
                            self.completeReport(post["_id"], True)
                            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": post["_id"]}})
                        # Give report feedback
                        self.completeReport(val, True)
                        # Send alert to user
                        self.createPost(post_origin="inbox", user=str(val), content="All your home posts have been deleted by a moderator. If you think this is a mistake, please contact the Meower moderation team.")
                        # Return to the client it's data
                        self.sendPacket({"cmd": "direct", "val": "", "id": client}, listener_detected = listener_detected, listener_id = listener_id)
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
                if accountData["lvl"] >= 1:
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
                if accountData["lvl"] >= 3:
                    if type(val) == str:
                        self.createPost(post_origin="inbox", user="Server", content=val)
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
    
    def block(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 2:
                    if type(val) == str:
                        result, payload = self.filesystem.load_item("config", "IPBanlist")
                        if result:
                            if val not in payload["wildcard"]:
                                self.log("Wildcard unblocking IP address {0}".format(val))
                                payload["wildcard"].append(val)
                                self.cl.blockIP(val)

                                # Kick all clients
                                FileRead, netlog = self.filesystem.load_item("netlog", val)
                                if FileRead:
                                    for user in netlog["users"]:
                                        if user in self.cl.getUsernames() and (self.cl.statedata["ulist"]["objs"][self.cl.statedata["ulist"]["usernames"][user]]["ip"] == val):
                                            self.supporter.kickUser(user, "Blocked")
                                
                            result = self.filesystem.write_item("config", "IPBanlist", payload)
                            if result:
                                self.sendPacket({"cmd": "direct", "val": "", "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Some other error, raise an internal error.
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
                if accountData["lvl"] >= 2:
                    if type(val) == str:
                        result, payload = self.filesystem.load_item("config", "IPBanlist")
                        if result:
                            if val in payload["wildcard"]:
                                self.log("Wildcard unblocking IP address {0}".format(val))
                                payload["wildcard"].remove(val)
                                self.cl.unblockIP(val)
                                
                            result = self.filesystem.write_item("config", "IPBanlist", payload)
                            if result:
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Some other error, raise an internal error.
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def kick(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 1:
                    if type(val) == str:
                        if val in self.cl.getUsernames():
                            # Revoke sessions
                            FileCheck, FileRead, FileWrite = self.accounts.update_setting(val, {"tokens": []}, forceUpdate=True)
                            if FileCheck and FileRead and FileWrite:
                                # Kick the user
                                self.supporter.kickUser(val)
                                
                                # Tell client it kicked the user
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def get_user_ip(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 2:
                    if type(val) == str:
                        FileCheck, FileRead, userdata = self.accounts.get_account(val)
                        if FileCheck and FileRead:
                            payload = {
                                "mode": "user_ip",
                                "payload": {
                                    "username": str(val),
                                    "ip": str(userdata["last_ip"])
                                }
                            }
                            self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
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
                if accountData["lvl"] >= 2:
                    if type(val) == str:
                        if self.filesystem.does_item_exist("netlog", str(val)):
                            result, netdata = self.filesystem.load_item("netlog", str(val))
                            if result:
                                result, banlist = self.filesystem.load_item("config", "IPBanlist")
                                if result:
                                    netdata["banned"] = (str(val) in banlist["wildcard"])
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

    def get_user_data(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 1:
                    if type(val) == str:
                        if self.accounts.account_exists(val):
                            FileCheck, FileRead, userdata = self.accounts.get_account(val, False, True)
                            if FileCheck and FileRead:
                                userdata["username"] = str(val)
                                payload = {
                                    "mode": "user_data",
                                    "payload": userdata
                                }
                                self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                if ((not FileCheck) and FileRead):
                                    # Account does not exist
                                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Some other error, raise an internal error.
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
    
    def ban(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 1:
                    if type(val) == str:
                        if self.accounts.account_exists(val):
                            FileCheck, FileRead, FileWrite = self.accounts.update_setting(val, {"banned": True}, forceUpdate=True)
                            if FileCheck and FileRead and FileWrite:
                                self.createPost(post_origin="inbox", user=val, content="Your account has been banned due to recent activity. If you think this is a mistake, please report this message and we will look further into it.")
                                self.log("Banning {0}".format(val))
                                # Kick client
                                self.supporter.kickUser(val, status="Banned")
                                
                                # Give report feedback
                                self.completeReport(val, True)

                                # Tell client it banned the user
                                self.sendPacket({"cmd": "direct", "val": "", "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # raise an internal error.
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
    
    def pardon(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 1:
                    if type(val) == str:
                        if self.accounts.account_exists(val):
                            FileCheck, FileRead, FileWrite = self.accounts.update_setting(val, {"banned": False}, forceUpdate=True)
                            if FileCheck and FileRead and FileWrite:
                                self.createPost(post_origin="inbox", user=val, content="Your account has been unbanned. Welcome back! Please make sure to follow the Meower community guidelines in the future, otherwise you may receive a more severe punishment.")
                                self.log("Pardoning {0}".format(val))
                                # Tell client it pardoned the user
                                self.sendPacket({"cmd": "direct", "val": "", "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # raise an internal error.
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
    
    def terminate(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
                if FileCheck and FileRead:
                    if accountData["lvl"] >= 3:
                        if self.filesystem.does_item_exist("usersv0", val):
                            # Delete all posts
                            post_index = self.getIndex("posts", {"u": str(val), "isDeleted": False}, truncate=False)
                            for post in post_index["index"]:
                                post["isDeleted"] = True
                                self.filesystem.write_item("posts", post["_id"], post)
                                if post["post_origin"] != "inbox":
                                    self.completeReport(post["_id"], True)
                                    self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": post["_id"]}})
                            FileCheck, FileRead, FileWrite = self.accounts.update_setting(val, {"banned": True}, forceUpdate=True)
                            if FileCheck and FileRead and FileWrite:
                                self.log("Terminating {0}".format(val))
                                # Kick the user
                                self.cl.kickClient(val, status="Banned")

                                # Give report feedback
                                self.completeReport(val, True)

                                # Tell client it terminated the user
                                self.sendPacket({"cmd": "direct", "val": "", "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Account not found
                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def repair_mode(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 4:
                    self.log("Enabling repair mode")
                    # Save repair mode status to database and memory
                    self.filesystem.write_item("config", "status", {"repair_mode": True, "is_deprecated": False})
                    self.supporter.status = {"repair_mode": True, "is_deprecated": False}
                    # Tell client it enabled repair mode
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                    # Kick all online users
                    self.log("Kicking all clients")
                    for username in self.cl.getUsernames():
                        try:
                            self.cl.kickClient(username)
                        except:
                            pass
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
        if self.supporter.isAuthenticated(client):
            if self.filesystem.does_item_exist("posts", val):
                result, payload = self.filesystem.load_item("posts", val)
                if result:
                    if (payload["post_origin"] != "inbox") and ((payload["u"] == client) or ((payload["u"] == "Discord") and payload["p"].startswith("{0}:".format(client)))):
                        payload["isDeleted"] = True
                        result = self.filesystem.write_item("posts", val, payload)
                        if result:
                            self.log("{0} deleting post {1}".format(client, val))

                            # Relay post deletion to clients
                            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}})
                            
                            # Return to the client the post was deleted
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
                        if FileCheck and FileRead:
                            if accountData["lvl"] >= 1:
                                if type(val) == str:
                                    payload["isDeleted"] = True
                                    result = self.filesystem.write_item("posts", val, payload)
                                    if result:
                                        self.log("{0} deleting post {1}".format(client, val))

                                        # Relay post deletion to clients
                                        self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}})

                                        # Create moderator alert
                                        if payload["post_origin"] != "inbox":
                                            self.createPost(post_origin="inbox", user=payload["u"], content="One of your posts were removed by a moderator because it violated the Meower terms of service! If you think this is a mistake, please report this message and we will look further into it. Post: '{0}'".format(payload["p"]))

                                            # Give report feedback
                                            self.completeReport(payload["_id"], True)

                                        # Return to the client the post was deleted
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Post not found
                self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
        else:



            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
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
            chat_index = self.getIndex(location="chats", query={"members": {"$all": [client]}}, truncate=True, sort="nickname")
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
                            if not username in chatdata["members"]:
                                chatdata["members"].append(username)
                                FileWrite = self.filesystem.write_item("chats", chatid, chatdata)

                                if FileWrite:
                                    # Inbox message to say the user was added to the group chat
                                    self.createPost("inbox", username, "You have been added to the group chat '{0}'!".format(chatdata["nickname"]))

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
                            if client != username:
                                # Remove user from group chat
                                chatdata["members"].remove(username)
                                result = self.filesystem.write_item("chats", chatid, chatdata)

                                if result:
                                    # Inbox message to say the user was removed from the group chat
                                    self.createPost("inbox", username, "You have been removed from the group chat '{0}'!".format(chatdata["nickname"]))

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

    def change_pswd(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not self.supporter.check_for_spam("password-change", client, burst=2, seconds=120):         
                    if len(val) > 64:
                        val = val[:64]
                    
                    # Change password
                    FileCheck, FileRead, FileWrite = self.accounts.change_password(client, val)

                    if FileCheck and FileRead and FileWrite:
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        self.returnCode(client = client, code = "Internal", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def del_tokens(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                FileCheck, FileRead, FileWrite = self.accounts.update_setting(client, {"tokens": []}, forceUpdate=True)
                if FileCheck and FileRead and FileWrite:
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def del_account(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] == 0:
                    all_posts = self.getIndex(location="posts", query={"u": client}, truncate=False)["index"]
                    for post in all_posts:
                        self.filesystem.delete_item("posts", post["_id"])
                        self.completeReport(post["_id"], None)
                        if post["post_origin"] != "inbox":
                            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": post["_id"]}})
                    chat_index = self.getIndex(location="chats", query={"members": {"$all": [client]}}, truncate=False)["index"]
                    for chat in chat_index:
                        if chat["owner"] == client:
                            self.filesystem.delete_item("chats", chat["_id"])
                            for member in chat["members"]:
                                if member in self.cl.getUsernames():
                                    self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": chat["_id"]}, "id": member})
                        else:
                            chat["members"].remove(client)
                            self.filesystem.write_item("chats", chat["_id"], chat)
                    netlog_index = self.getIndex(location="netlog", query={"users": {"$all": [client]}}, truncate=False)["index"]
                    for ip in netlog_index:
                        ip["users"].remove(client)
                        if len(ip["users"]) == 0:
                            self.filesystem.delete_item("netlog", ip["_id"])
                        else:
                            if ip["last_user"] == client:
                                ip["last_user"] = ip["users"][(len(ip["users"])-1)]
                            self.filesystem.write_item("netlog", ip["_id"], ip)
                    self.filesystem.delete_item("usersv0", client)
                    self.completeReport(client, None)
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                    time.sleep(1)
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

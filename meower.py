import time
import uuid

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
    
    def getIndex(self, location="posts", query={"post_origin": "home", "isDeleted": False},  truncate=False, page=1):
        query_get = self.filesystem.find_items(location, query)
        query_get.reverse()
        
        if truncate:
            # Truncate results
            if len(query_get) == 0:
                pages = 0
            else:
                if (len(query_get) % 25) == 0:
                    if (len(query_get) < 25):
                        pages = 1
                    else:
                        pages = (len(query_get) // 25)
                else:
                    pages = (len(query_get) // 25)+1
            
            query_return = query_get[((page*25)-25):page*25]
        else:
            if len(query_get) == 0:
                pages = 0
            else:
                pages = 1
            query_return = query_get
        
        query_return = {
            "query": query,
            "index": query_return,
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
                # Implement code below once client is updated
                #payload = {
                    #"mode": "post",
                    #"payload": post_data
                #}

                # Remove code below once client is updated
                payload = post_data
                payload["mode"] = 1

                self.cl.sendPacket({"cmd": "direct", "val": payload})
                return True
            else:
                return False
        elif post_origin == "announcement":
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
                    "mode": "inbox_announcement",
                    "payload": post_data
                }

                self.cl.sendPacket({"cmd": "direct", "val": payload})
                return True
            else:
                return False
        elif post_origin == "inbox":
            post_data = {
                "type": 3,
                "post_origin": str(post_origin), 
                "u": str(user), 
                "t": timestamp, 
                "p": str(content), 
                "post_id": post_id, 
                "isDeleted": False
            }

            result = self.filesystem.create_item("posts", post_id, post_data)

            if result:
                if user in self.cl.getUsernames():
                    payload = {
                        "mode": "inbox_message",
                        "payload": post_data
                    }

                    self.cl.sendPacket({"cmd": "direct", "val": payload})
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

            # Implement code below once client is updated
            #payload = {
                #"mode": "post",
                #"payload": post_data
            #}

            # Remove code below once client is updated
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
                    # Implement code below once client is updated
                    #payload = {
                        #"mode": "post",
                        #"payload": post_data
                    #}

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
    
    def returnCode(self, client, code, listener_detected, listener_id):
        self.sendPacket({"cmd": "statuscode", "val": self.cl.codes[str(code)], "id": client}, listener_detected = listener_detected, listener_id = listener_id)
    
    # Networking/client utilities
    
    def ping(self, client, listener_detected, listener_id):
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
    
    # Accounts and security
    
    def authpswd(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if not self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if ("username" in val) and ("pswd" in val):
                    
                    # Extract username and password for simplicity
                    username = val["username"]
                    password = val["pswd"]
                    
                    if ((type(username) == str) and (type(password) == str)):
                        if not self.supporter.checkForBadCharsUsername(username):
                            if not self.supporter.checkForBadCharsPost(password):
                                FileCheck, FileRead, Banned = self.accounts.is_account_banned(username)
                                if not Banned:
                                    if FileCheck and FileRead:
                                        FileCheck, FileRead, ValidAuth = self.accounts.authenticate(username, password)
                                        if FileCheck and FileRead:
                                            if ValidAuth:
                                                self.supporter.kickBadUsers(username) # Kick bad clients missusing the username
                                                self.filesystem.create_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), {"users": [], "last_user": username})
                                                status, netlog = self.filesystem.load_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]))
                                                if status:
                                                    if not username in netlog["users"]:
                                                        netlog["users"].append(username)
                                                    netlog["last_user"] = username
                                                    self.filesystem.write_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), netlog)
                                                    self.accounts.update_setting(username, {"last_ip": str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"])}, forceUpdate=True)
                                                    self.supporter.autoID(client, username) # If the client is JS-based then give them an AutoID
                                                    self.supporter.setAuthenticatedState(client, True) # Make the server know that the client is authed
                                                    # Return info to sender
                                                    payload = {
                                                        "mode": "auth",
                                                        "payload": {
                                                            "username": username
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
                                        if ((not FileCheck) and FileRead):
                                            # Account does not exist
                                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                                        else:
                                            # Some other error, raise an internal error.
                                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Account banned
                                    self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)
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
                    
                    if ((type(username) == str) and (type(password) == str)):
                        if not self.supporter.checkForBadCharsUsername(username):
                            if not self.supporter.checkForBadCharsPost(password):
                                FileCheck, FileWrite = self.accounts.create_account(username, password)
                                
                                if FileCheck and FileWrite:
                                    self.supporter.kickBadUsers(username) # Kick bad clients missusing the username
                                    self.filesystem.create_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), {"users": [], "last_user": username})
                                    status, netlog = self.filesystem.load_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]))
                                    if status:
                                        if not username in netlog["users"]:
                                            netlog["users"].append(username)
                                        netlog["last_user"] = username
                                        self.filesystem.write_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), netlog)
                                        self.accounts.update_setting(username, {"last_ip": str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"])}, forceUpdate=True)
                                        self.supporter.autoID(client, username) # If the client is JS-based then give them an AutoID
                                        self.supporter.setAuthenticatedState(client, True) # Make the server know that the client is authed
                                        
                                        # Return info to sender
                                        payload = {
                                            "mode": "auth",
                                            "payload": username
                                        }
                                        
                                        self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                        
                                        # Tell the client it is authenticated
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                        
                                        # Log peak users
                                        self.supporter.log_peak_users()

                                        # Send welcome message
                                        self.createPost(post_origin="inbox", user=username, content="Welcome to Meower! We hope you enjoy it here :)")
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
            if (type(val) == dict) and ("page" in val) and (type(val["page"]) == int):
                page = val["page"]
            else:
                page = 1
            home_index = self.getIndex("posts", {"post_origin": "home", "isDeleted": False}, truncate=True, page=page)
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
                    if self.supporter.check_for_spam(client):
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
                            if payload["type"] == 1:
                                if payload["post_origin"] == "home":
                                    hasPermission = True
                                else:
                                    result, chatdata = self.filesystem.load_item("chats", payload["post_origin"])
                                    if result:
                                        if client in chatdata["members"]:
                                            hasPermission = True
                            elif payload["type"] == 2:
                                hasPermission = True
                            elif payload["type"] == 3:
                                if payload["u"] == client:
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
    
    def get_peak_users(self, client, listener_detected, listener_id):
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
                    if ("page" in val) and (type(val["page"]) == int):
                        try:
                            index = self.getIndex(location="posts", query={"post_origin": "home", "u": val["query"], "isDeleted": False}, page=val["page"])
                            payload = {
                                "mode": "user_posts",
                                "index": index
                            }
                            self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        except:
                            self.log("{0}".format(self.errorhandler()))
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        try:
                            index = self.getIndex(location="posts", query={"post_origin": "home", "u": val["query"], "isDeleted": False}, page=1)
                            payload = {
                                "mode": "user_posts",
                                "index": index
                            }
                            self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        except:
                            self.log("{0}".format(self.errorhandler()))
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
    
    # Moderator features
    
    def clear_home(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 1:
                    if (type(val) == dict) and ("page" in val) and (type(val["page"]) == int):
                        page = val["page"]
                    else:
                        page = 1
                    home_index = self.getIndex("posts", {"post_origin": "home", "isDeleted": False}, truncate=True, page=page)
                    for post_id in home_index["index"]:
                        result, payload = self.filesystem.load_item("posts", post_id)
                        if result:
                            payload["isDeleted"] = True
                            result = self.filesystem.write_item("posts", post_id, payload)
                    # Return to the client it's data
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
                    if accountData["lvl"] >= 2:
                        post_index = self.getIndex("posts", {"type": 1, "u": str(val), "isDeleted": False}, truncate=False)
                        for post_id in post_index["index"]:
                            result, payload = self.filesystem.load_item("posts", post_id)
                            if result:
                                payload["isDeleted"] = True
                                result = self.filesystem.write_item("posts", post_id, payload)
                        # Send alert to user
                        self.createPost(post_origin="inbox", user=str(val), content="All your posts have been deleted by a moderator.")
                        # Return to the client it's data
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
                            if self.accounts.account_exists(val["username"]):
                                self.createPost(post_origin="inbox", user=val["username"], content="Message from Meower Team: {0}".format(val["p"]))
                            else:
                                # Account not found
                                self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
                        self.createPost(post_origin="announcement", user=client, content="Announcement from {0}: {1}".format(client, val))
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
                    result, payload = self.filesystem.load_item("config", "IPBanlist")
                    if result:
                        if type(val) == str:
                            if not val in payload["wildcard"]:
                                payload["wildcard"].append(val)
                                result = self.filesystem.write_item("config", "IPBanlist", payload)
                                if result:
                                    self.log("Wildcard blocking IP address {0}".format(val))
                                    self.cl.blockIP(val)
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Some other error, raise an internal error.
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Bad datatype
                            self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Some other error, raise an internal error.
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
                    result, payload = self.filesystem.load_item("config", "IPBanlist")
                    if result:
                        if type(val) == str:
                            if val in payload["wildcard"]:
                                payload["wildcard"].remove(val)
                                result = self.filesystem.write_item("config", "IPBanlist", payload)
                                if result:
                                    self.log("Wildcard unblocking IP address {0}".format(val))
                                    self.cl.unblockIP(val)
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Some other error, raise an internal error.
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Bad datatype
                            self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Some other error, raise an internal error.
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
                            # Tell client it's going to get kicked
                            self.sendPacket({"cmd": "direct", "val": self.cl.codes["Kicked"], "id": val})
                            
                            time.sleep(1)
                            self.log("Kicking {0}".format(val))
                            
                            self.cl.kickClient(val)
                            
                            # Tell client it kicked the user
                            self.sendPacket({"cmd": "direct", "val": "", "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            
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
                if accountData["lvl"] >= 2:
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
                                self.createPost(post_origin="inbox", user=val, content="Your account has been banned due to recent activity.")
                                self.log("Banning {0}".format(val))
                                # Tell client it's going to get banned
                                self.sendPacket({"cmd": "direct", "val": self.cl.codes["Banned"], "id": val})
                                
                                time.sleep(1)
                                self.log("Kicking {0}".format(val))
                                
                                self.cl.kickClient(val)
                                
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
                                self.createPost(post_origin="inbox", user=val, content="Your account has been unbanned. Welcome back!")
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
                    if accountData["lvl"] >= 4:
                        if self.filesystem.does_item_exist("usersv0", val):
                            all_posts = self.getIndex(location="posts", query={"u": val}, truncate=False)["index"]
                            for post_id in all_posts:
                                result, payload = self.filesystem.load_item("posts", post_id)
                                if result:
                                    payload["isDeleted"] = True
                                    self.filesystem.write_item("posts", post_id, payload)
                            FileCheck, FileRead, FileWrite = self.accounts.update_setting(val, {"theme": None, "mode": None, "sfx": None, "debug": None, "bgm": None, "bgm_song": None, "layout": None, "pfp_data": None, "quote": None, "email": None, "pswd": None, "lvl": None, "banned": True, "last_ip": None}, forceUpdate=True)
                            if FileCheck and FileRead and FileWrite:
                                self.log("Terminating {0}".format(val))
                                # Tell client it's going to get terminated
                                self.sendPacket({"cmd": "direct", "val": self.cl.codes["Banned"], "id": val})
                                
                                time.sleep(1)
                                self.log("Kicking {0}".format(val))
                                
                                self.cl.kickClient(val)
                                
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

    def ip_ban(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 2:
                    if type(val) == str:
                        result, payload = self.filesystem.load_item("config", "IPBanlist")
                        if result:
                            FileCheck, FileRead, userdata = self.accounts.get_account(val)
                            if FileCheck and FileRead:
                                userIP = userdata["last_ip"]
                                if not str(val) in payload["users"]:
                                    payload["users"][str(val)] = str(userIP)
                                    
                                    if not str(userIP) in payload["wildcard"]:
                                        payload["wildcard"].append(str(userIP))

                                    result = self.filesystem.write_item("config", "IPBanlist", payload)
                                    if result:
                                        self.log("IP Banning {0}".format(val))
                                        self.cl.blockIP(userIP)
                                        # Tell client it's going to get IP blocked
                                        self.sendPacket({"cmd": "direct", "val": self.cl.codes["Blocked"], "id": val})
                                        
                                        time.sleep(1)
                                        self.log("Kicking {0}".format(val))
                                        
                                        self.cl.kickClient(val)
                                        
                                        # Tell client it banned the user
                                        self.sendPacket({"cmd": "direct", "val": "", "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        # Some other error, raise an internal error.
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                if ((not FileCheck) and FileRead):
                                    # Account does not exist
                                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def ip_pardon(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 2:
                    if type(val) == str:
                        result, payload = self.filesystem.load_item("config", "IPBanlist")
                        if result:
                            if val in payload["users"]:
                                userIP = payload["users"][val]
                                if str(val) in payload["users"]:
                                    del payload["users"][str(val)]
                                    
                                    if str(userIP) in payload["wildcard"]:
                                        payload["wildcard"].remove(str(userIP))
                                    
                                    result = self.filesystem.write_item("config", "IPBanlist", payload)
                                    if result:
                                        self.log("IP Pardoning {0}".format(val))
                                        self.cl.unblockIP(userIP)
                                        # Tell client it banned the user
                                        self.sendPacket({"cmd": "direct", "val": "", "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        # Some other error, raise an internal error.
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # User not found
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
    
    def repair_mode(self, client, listener_detected, listener_id):
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
                        self.cl.kickClient(username)
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
                    if payload["u"] == client:
                        payload["isDeleted"] = True
                        result = self.filesystem.write_item("posts", val, payload)
                        if result:
                            self.log("{0} deleting home post {1}".format(client, val))

                            # Relay post to clients
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
                                        self.log("{0} deleting home post {1}".format(client, val))

                                        # Relay post to clients
                                        self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}})

                                        # Create moderator alert
                                        result, payload = self.filesystem.load_item("posts", val)
                                        if result:
                                            self.createPost(post_origin="inbox", user=payload["u"], content="One of your posts were removed by a moderator! Post: '{0}'".format(payload["p"]))

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
                    
                    if not self.supporter.checkForBadCharsUsername(val):
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
                        # Bad characters being used
                        self.returnCode(client = client, code = "IllegalChars", listener_detected = listener_detected, listener_id = listener_id)
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
                    
                    if not self.supporter.checkForBadCharsUsername(val):
                        if self.filesystem.does_item_exist("chats", val):
                            result, payload = self.filesystem.load_item("chats", val)
                            if result:
                                if client in payload["members"]:
                                    if payload["owner"] == client:
                                        result = self.filesystem.delete_item("chats", val)
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
                        # Bad characters being used
                        self.returnCode(client = client, code = "IllegalChars", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Too large
                    self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def get_chat_list(self, client, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            chat_index = self.getIndex(location="chats", query={"members": {"$all": [client]}}, truncate=True)
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

    # Kinda want to deprecate :/ -- has no permission checking because it's kinda useless and I hope it gets deprecated anyway
    def set_chat_state(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if (type(val) == dict) and (("state" in val) and (type(val["state"]) == int)) and (("chatid" in val) and (type(val["chatid"]) == str)):
                
                state = val["state"]
                chatid = val["chatid"]
                
                if not len(chatid) > 50:
                    if self.supporter.check_for_spam(client):
                        
                        # Create post format
                        post_w_metadata = {}
                        post_w_metadata["state"] = state
                        post_w_metadata["u"] = str(client)
                        post_w_metadata["chatid"] = str(chatid)
                        
                        self.log("{0} modifying {1} state to {2}".format(client, chatid, state))
                        
                        self.sendPacket({"cmd": "direct", "val": post_w_metadata})
                        
                        # Tell client message was sent
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        
                        self.supporter.ratelimit(client)
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
    
    def post_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if (type(val) == dict) and (("p" in val) and (type(val["p"]) == str)) and (("chatid" in val) and (type(val["chatid"]) == str)):
                post = val["p"]
                chatid = val["chatid"]
                if (not len(post) > 360) and (not len(chatid) > 50):
                    if self.supporter.check_for_spam(client):
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
                    result, chatdata = self.filesystem.load_item("chats", chatid)
                    if result:
                        if client in chatdata["members"]:
                            # Add user to group chat
                            chatdata["members"].append(username)
                            result = self.filesystem.write_item("chats", chatid, chatdata)

                            if result:
                                # Inbox message to say the user was added to the group chat
                                self.createPost(post_origin="inbox", user=username, content="You have been added to the group chat '{0}'!".format(chatdata["nickname"]))

                                # Tell client user was added
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Some other error, raise an internal error.
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
                                    self.createPost(post_origin="inbox", user=username, content="You have been removed from the group chat '{0}'!".format(chatdata["nickname"]))

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
                if ("page" in val) and (type(val["page"]) == int):
                    inbox_index = self.getIndex(location="posts", query={"post_origin": "inbox", "u": client}, page=val["page"])
                    payload = {
                        "mode": "inbox",
                        "payload": inbox_index
                    }
                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    inbox_index = self.getIndex(location="posts", query={"post_origin": "inbox", "u": client}, page=1)
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

    def get_announcements(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == dict:
                if ("page" in val) and (type(val["page"]) == int):
                    announcements_index = self.getIndex(location="posts", query={"post_origin": "announcement"}, page=val["page"])
                    payload = {
                        "mode": "announcements",
                        "payload": announcements_index
                    }
                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    announcements_index = self.getIndex(location="posts", query={"post_origin": "announcement"}, page=1)
                    payload = {
                        "mode": "announcements",
                        "payload": announcements_index
                    }
                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)

    def del_account(self, client, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] < 1:
                    all_posts = self.getIndex(location="posts", query={"u": client}, truncate=False)["index"]
                    for post_id in all_posts:
                        result, payload = self.filesystem.load_item("posts", post_id)
                        if result:
                            payload["u"] = "Deleted"
                            payload["p"] = "[This user was deleted - GDPR]"
                            payload["isDeleted"] = True
                            self.filesystem.write_item("posts", post_id, payload)
                    chat_index = self.getIndex(location="chats", query={"members": {"$all": [client]}}, truncate=False)["index"]
                    for chat_id in chat_index:
                        result, payload = self.filesystem.load_item("chats", chat_id)
                        if result:
                            if payload["owner"] == client:
                                self.filesystem.delete_item("chats", chat_id)
                            else:
                                payload["members"].remove(client)
                                self.filesystem.write_item("chats", chat_id, payload)
                    netlog_index = self.getIndex(location="netlog", query={"users": {"$all": [client]}}, truncate=False)["index"]
                    for ip in netlog_index:
                        result, payload = self.filesystem.load_item("netlog", ip)
                        if result:
                            payload["users"].remove(client)
                            if payload["last_user"] == client:
                                payload["last_user"] = "Deleted"
                            self.filesystem.write_item("netlog", ip, payload)
                    result = self.filesystem.delete_item("usersv0", client)
                    if result:
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        time.sleep(1)
                        self.cl.kickClient(client)
                    else:
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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

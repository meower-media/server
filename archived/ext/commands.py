import secrets
import time
import uuid

class WSCommands:
    def __init__(self, meower):
        self.cl = meower.cl
        self.supporter = meower.supporter
        self.log = meower.supporter.log
        self.errorhandler = meower.supporter.full_stack
        self.accounts = meower.accounts
        self.filesystem = meower.files
        self.sendPacket = meower.supporter.sendPacket
        self.log("Meower initialized!")
    
    def sendPayload(self, client, mode, payload):
        if client is None:
            self.sendPacket({"cmd": "direct", "val": {"mode": mode, "payload": payload}}, listener_detected = False, listener_id = None)
        else:
            self.sendPacket({"cmd": "direct", "val": {"mode": mode, "payload": payload}, "id": client}, listener_detected = False, listener_id = None)

    def returnCode(self, client, code, listener_detected, listener_id):
        self.sendPacket({"cmd": "statuscode", "val": self.cl.codes[str(code)], "id": client}, listener_detected = listener_detected, listener_id = listener_id)
    
    def abruptLogout(self, username, payload):
        if username in self.cl.getUsernames():
            self.sendPayload(username, "abrupt_logout", payload)
            client_id = self.cl.statedata["ulist"]["usernames"][username]
            del self.cl.statedata["ulist"]["usernames"][username]
            self.supporter.modify_client_statedata(username, "authed", False)
            time.sleep(0.5)
            self.cl.kickClient(username)

    # Networking/client utilities
    
    def ping(self, client, val, listener_detected, listener_id):
        # Returns your ping for my pong
        self.returnCode(client = client, code = "Pong", listener_detected = listener_detected, listener_id = listener_id)
    
    def version_chk(self, client, val, listener_detected, listener_id):
        if not type(val) == str:
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        # Load the supported versions list
        FileRead, supported_versions = self.filesystem.load_item("config", "supported_versions")
        if not FileRead:
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)  
        if val in supported_versions["index"]:
            # If the client version string exists in the list, it is supported
            return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Either unsupported or out of date
            return self.returnCode(client = client, code = "ObsoleteClient", listener_detected = listener_detected, listener_id = listener_id)  
    
    # Accounts and security

    def gen_code(self, client, val, listener_detected, listener_id):
        client_statedata = self.supporter.get_client_statedata(client)
        if client_statedata["login_code"] != None:
            del self.cl.statedata["ulist"]["login_codes"][client_statedata["login_code"]]

        # Generate a random code
        code = None
        while not ((code in self.cl.statedata["ulist"]["login_codes"]) or (code is None)):
            code = str(secrets.SystemRandom().randint(111111,999999))

        # Store the code
        self.supporter.modify_client_statedata(client, "login_code", code)
        self.cl.statedata["ulist"]["login_codes"][code] = client

        # Return the code to the client
        self.sendPacket({"cmd": "direct", "val": code, "id": client}, listener_detected = listener_detected, listener_id = listener_id)

        # Tell the client that the code was sent
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def auth(self, client, val, listener_detected, listener_id):
        client_statedata = self.supporter.get_client_statedata(client)
        if client_statedata["login_code"] != None:
            del self.cl.statedata["ulist"]["login_codes"][client_statedata["login_code"]]
        if self.supporter.isAuthenticated(client):
            # Already authenticated
            return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        elif not (type(val) == str):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif len(val) > 100:
            # Token too large
            return self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)

        file_read, token_data = self.accounts.get_token(val)
        if not file_read:
            # Bad characters being used
            return self.returnCode(client = client, code = "PasswordInvalid", listener_detected = listener_detected, listener_id = listener_id)

        # Authenticate client
        #self.supporter.kickBadUsers(token_data["u"]) # Kick bad clients missusing the username
        self.supporter.autoID(client, token_data["u"]) # Set ID for the client
        self.supporter.setAuthenticatedState(client, True) # Make the server know that the client is authed

        # Return info to sender
        payload = {
            "mode": "auth",
            "payload": {
                "username": token_data["u"]
            }
        }
        self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
        
        # Tell the client it is authenticated
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        
        # Log peak users
        self.supporter.log_peak_users()

    def authpswd(self, client, val, listener_detected, listener_id):
        if self.supporter.isAuthenticated(client):
            # Already authenticated
            return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        elif not (type(val) == dict):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif not (("username" in val) and ("pswd" in val)):
            # Bad syntax
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        elif not ((type(val["username"]) == str) and (type(val["pswd"]) == str)):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif (len(val["username"]) > 20) or (len(val["pswd"]) > 72):
            # Username or password too long
            return self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
        elif self.supporter.checkForBadCharsUsername(val["username"]) or self.supporter.checkForBadCharsPost(val["pswd"]):
            # Bad characters being used
            return self.returnCode(client = client, code = "IllegalChars", listener_detected = listener_detected, listener_id = listener_id)

        # Extract username and password for simplicity
        username = val["username"]
        password = val["pswd"]

        FileCheck, FileRead, Flags = self.accounts.get_flags(username)
        if not (FileCheck and FileRead):
            if ((not FileCheck) and FileRead):
                # Account does not exist
                return self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Some other error, raise an internal error
                return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        elif Flags["perm_locked"]:
            # Account permanently locked
            return self.returnCode(client = client, code = "PermLocked", listener_detected = listener_detected, listener_id = listener_id)
        elif Flags["locked"]:
            # Account temporarily locked
            return self.returnCode(client = client, code = "Locked", listener_detected = listener_detected, listener_id = listener_id)
        elif Flags["dormant"]:
            # Account dormant
            return self.returnCode(client = client, code = "Dormant", listener_detected = listener_detected, listener_id = listener_id)
        elif Flags["deleted"]:
            # Account deleted
            return self.returnCode(client = client, code = "Deleted", listener_detected = listener_detected, listener_id = listener_id)
        elif (self.accounts.authenticate(username, password) != (True, True, True)):
            # Password invalid
            return self.returnCode(client = client, code = "PasswordInvalid", listener_detected = listener_detected, listener_id = listener_id)
        elif Flags["banned"]:
            # Account banned
            return self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)
        elif Flags["pending_deletion"]:
            # Account restoration
            self.accounts.update_setting(username, {"flags.delete_after": None}, forceUpdate=True)
            self.createPost(post_origin="inbox", user=username, content={"h": "Account Alert", "p": "Your account was about to be deleted but you logged in! Your account has been restored. If you weren't the one to request your account to be deleted, please change your password immediately."})
    
        # Update netlog data
        self.filesystem.create_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), {"users": [], "last_user": username})
        FileRead, netlog = self.filesystem.load_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]))
        if not FileRead:
            # Some other error, raise an internal error
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        if not username in netlog["users"]:
            netlog["users"].append(username)
        netlog["last_user"] = username
        self.filesystem.write_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), netlog)
        self.accounts.update_setting(username, {"last_login": int(time.time()), "last_ip": str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"])}, forceUpdate=True)

        # Authenticate client
        self.supporter.kickBadUsers(username) # Kick bad clients missusing the username
        self.supporter.autoID(client, username) # Set ID for the client
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

    def gen_account(self, client, val, listener_detected, listener_id):
        if self.supporter.isAuthenticated(client):
            # Already authenticated
            return self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
        elif not (type(val) == dict):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif not (("username" in val) and ("pswd" in val)):
            # Bad syntax
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        elif not ((type(val["username"]) == str) and (type(val["pswd"]) == str)):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif (len(val["username"]) > 20) or (len(val["pswd"]) > 72):
            # Username or password too long
            return self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
        elif self.supporter.checkForBadCharsUsername(val["username"]) or self.supporter.checkForBadCharsPost(val["pswd"]):
            # Bad characters being used
            return self.returnCode(client = client, code = "IllegalChars", listener_detected = listener_detected, listener_id = listener_id)

        # Extract username and password for simplicity
        username = val["username"]
        password = val["pswd"]

        FileCheck, FileWrite = self.accounts.create_account(username, password)
        if not (FileCheck and FileWrite):
            if ((not FileCheck) and FileWrite):
                # Account does not exist
                return self.returnCode(client = client, code = "IDExists", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Some other error, raise an internal error
                return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)

        # Update netlog data
        self.filesystem.create_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), {"users": [], "last_user": username})
        FileRead, netlog = self.filesystem.load_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]))
        if not FileRead:
            # Some other error, raise an internal error
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        if not username in netlog["users"]:
            netlog["users"].append(username)
        netlog["last_user"] = username
        self.filesystem.write_item("netlog", str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"]), netlog)
        self.accounts.update_setting(username, {"last_ip": str(self.cl.statedata["ulist"]["objs"][client["id"]]["ip"])}, forceUpdate=True)

        # Authenticate client
        self.supporter.kickBadUsers(username) # Kick bad clients missusing the username
        self.supporter.autoID(client, username, "pswd") # Set ID for the client
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

        # Send welcome message
        self.createPost(post_origin="inbox", user=username, content={"h": "Welcome to Meower", "p": "Welcome to Meower! We welcome you with open arms! You can get started by making friends in the global chat or home, or by searching for people and adding them to a group chat. We hope you have fun!"})
    
    def get_profile(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                FileRead, Payload = self.accounts.get_account(val)
                
                if FileRead:
                    payload = {
                        "mode": "profile",
                        "payload": Payload["userdata"],
                        "user_id": val
                    }
                    
                    self.log("{0} fetching profile {1}".format(client, val))
                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                    
                    # Return to the client it's data
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    if not FileRead:
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
                FileRead, Payload = self.accounts.get_account(client)
                if FileRead:
                    self.log("{0} updating config".format(client))
                    FileWrite = self.accounts.update_config(client, val)
                    if FileRead and FileWrite:
                        # OK
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # raise an internal error.
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    if not FileRead:
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
            home_index = self.filesystem.find_items("posts", {"post_origin": "home", "isDeleted": False}, sort="t.e", truncate=True, page=page)
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
                            if payload["post_origin"] == "home":
                                hasPermission = True
                            elif payload["post_origin"] == "inbox":
                                if payload["u"] == "Server" or payload["u"] == client:
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
                    home_index = self.filesystem.find_items("posts", {"post_origin": "home", "isDeleted": False}, sort="t.e", truncate=True, page=page)
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

    def alert(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 1:
                    if type(val) == dict:
                        if ("username" in val) and ("p" in val):
                            if self.accounts.account_exists(val["username"]):
                                self.createPost(post_origin="inbox", user=val["username"], content={"h": "Moderator Alert", "p": val["p"]})
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
                        self.createPost(post_origin="inbox", user="Server", content={"h": "Announcement", "p": val})
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
                            FileCheck, FileWrite = self.accounts.update_setting(val, {"banned": True}, forceUpdate=True)
                            if FileCheck and FileRead and FileWrite:
                                self.createPost(post_origin="inbox", user=val, content={"h": "Moderator Alert", "p": "Your account has been banned due to recent activity. If you think this is a mistake please contact the Meower Team."})
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
                            FileCheck, FileWrite = self.accounts.update_setting(val, {"banned": False}, forceUpdate=True)
                            if FileCheck and FileRead and FileWrite:
                                self.createPost(post_origin="inbox", user=val, content={"h": "Moderator Alert", "p": "Your account has been unbanned. Welcome back! Please make sure to follow the Meower community guidelines in the future otherwise you may receive more severe punishments."})
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
                            all_posts = self.filesystem.find_items("posts", {"u": val}, truncate=False)
                            for post_id in all_posts:
                                result, payload = self.filesystem.load_item("posts", post_id)
                                if result:
                                    payload["isDeleted"] = True
                                    self.filesystem.write_item("posts", post_id, payload)
                            FileCheck, FileWrite = self.accounts.update_setting(val, {"banned": True}, forceUpdate=True)
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
    
    def repair_mode(self, val, client, listener_detected, listener_id):
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
                            self.log("{0} deleting post {1}".format(client, val))

                            # Relay post to clients
                            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}})
                            
                            # Return to the client the post was deleted
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
                        if FileCheck and FileRead:
                            if accountData["lvl"] >= 1 and payload["post_origin"] != "inbox":
                                if type(val) == str:
                                    payload["isDeleted"] = True
                                    result = self.filesystem.write_item("posts", val, payload)
                                    if result:
                                        self.log("{0} deleting post {1}".format(client, val))

                                        # Relay post to clients
                                        if payload["type"] == 3:
                                            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}, "id": payload["u"]})
                                        else:
                                            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}})

                                        # Create moderator alert
                                        if payload["type"] == 1:
                                            self.createPost(post_origin="inbox", user=payload["u"], content={"h": "Moderator Alert", "p": "One of your posts were removed by a moderator! Please make sure to follow the Meower community guidelines in the future, otherwise your account may be suspended/banned. Post: '{0}'".format(payload["p"])})

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
                            result = self.filesystem.create_item("chats", str(uuid.uuid4()), {"nickname": val, "owner": client, "members": [client], "added_by": {client: client}})
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
                                        payload["members"].remove(client)
                                        if len(payload["members"]) > 0:
                                            payload["owner"] = payload["members"][0]
                                            result = self.filesystem.write_item("chats", val, payload)
                                            self.createPost(post_origin="inbox", user=payload["owner"], content={"h": "Notification", "p": "You have been given ownership of the group chat '{0}'!".format(payload["nickname"])})
                                        else:
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
    
    def get_chat_list(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            chat_index = self.filesystem.find_items("chats", {"members": {"$all": [client]}}, sort="nickname", truncate=True, page=1)
            chat_index["all_chats"] = []
            for item in chat_index["index"]:
                FileRead, chatdata = self.filesystem.load_item("chats", item)
                if FileRead:
                    chatdata["chatid"] = item
                    del chatdata["_id"]
                    chat_index["all_chats"].append(chatdata)
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
                                del chatdata["_id"]
                                payload = {
                                    "mode": "chat_data",
                                    "payload": chatdata
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
                                posts_index = self.filesystem.find_items("posts", {"post_origin": val, "isDeleted": False}, sort="t.e", truncate=True, page=1)
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
        elif not ((type(val) == dict) and (("state" in val) and (type(val["state"]) == int)) and (("chatid" in val) and (type(val["chatid"]) == str))):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif len(val["chatid"]) > 50:
            # Chat ID too long
            return self.returnCode(client = client, code = "TooLarge", listener_detected = listener_detected, listener_id = listener_id)
        elif not self.supporter.check_for_spam(client):
            # Rate limiter
            return self.returnCode(client = client, code = "RateLimit", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract state and chat ID for simplicity
        state = val["state"]
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
        if not self.supporter.isAuthenticated(client):
            # Not authenticated
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        elif not (type(val) == dict):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif not (("username" in val) and ("chatid" in val)):
            # Bad syntax
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        elif not ((type(val["username"]) == str) and (type(val["chatid"]) == str)):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract username and chat ID for simplicity
        username = val["username"]
        chatid = val["chatid"]

        # Read chat data 
        FileRead, chatdata = self.filesystem.load_item("chats", chatid)
        if not FileRead:
            # Some other error, raise an internal error
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        elif not (client in chatdata["members"]):
            # User not in chat
            return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
        
        # Add user to chat
        if not (username in chatdata["members"]):
            chatdata["members"].append(username)
            chatdata["added_by"][username] = client
            FileWrite = self.filesystem.write_item("chats", chatid, chatdata)
            if not FileWrite:
                # Some other error, raise an internal error
                return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
            
            # Inbox message to say the user was added to the group chat
            self.createPost(post_origin="inbox", user=username, content={"h": "Notification", "p": "You have been added to the group chat '{0}'!".format(chatdata["nickname"])})

        # Tell client user was added
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def remove_from_chat(self, client, val, listener_detected, listener_id):
        if not self.supporter.isAuthenticated(client):
            # Not authenticated
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        elif not (type(val) == dict):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif not (("username" in val) and ("chatid" in val)):
            # Bad syntax
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        elif not ((type(val["username"]) == str) and (type(val["chatid"]) == str)):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract username and chat ID for simplicity
        username = val["username"]
        chatid = val["chatid"]
                    
        # Read chat data
        FileRead, chatdata = self.filesystem.load_item("chats", chatid)
        if not FileRead:
            # Some other error, raise an internal error
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        elif not (client == chatdata["owner"]):
            # User is not owner of chat
            return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
        elif client == username:
            # Stop user from removing themself
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Remove user from chat
        if username in chatdata["members"]:
            chatdata["members"].remove(username)
            FileWrite = self.filesystem.write_item("chats", chatid, chatdata)
            if not FileWrite:
                # Some other error, raise an internal error
                return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)

            # Inbox message to say the user was removed from the group chat
            self.createPost(post_origin="inbox", user=username, content={"h": "Notification", "p": "You have been removed from the group chat '{0}'!".format(chatdata["nickname"])})

        # Tell client user was removed
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def transfer_ownership(self, client, val, listener_detected, listener_id):
        if not self.supporter.isAuthenticated(client):
            # Not authenticated
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        elif not (type(val) == dict):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        elif not (("username" in val) and ("chatid" in val)):
            # Bad syntax
            return self.returnCode(client = client, code = "Syntax", listener_detected = listener_detected, listener_id = listener_id)
        elif not ((type(val["username"]) == str) and (type(val["chatid"]) == str)):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        
        # Extract username and chat ID for simplicity
        username = val["username"]
        chatid = val["chatid"]
                    
        # Read chat data
        FileRead, chatdata = self.filesystem.load_item("chats", chatid)
        if not FileRead:
            # Some other error, raise an internal error
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        elif not (client == chatdata["owner"]):
            # User is not owner of chat
            return self.returnCode(client = client, code = "MissingPermissions", listener_detected = listener_detected, listener_id = listener_id)
        elif client == username:
            # Stop user from removing themself
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        elif not (username in chatdata["members"]):
            # Stop user from giving ownership to someone that is not in the chat
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        
        # Give ownership of chat
        chatdata["owner"] = username
        FileWrite = self.filesystem.write_item("chats", chatid, chatdata)
        if not FileWrite:
            # Some other error, raise an internal error
            return self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)

        # Inbox message to say the user was removed from the group chat
        self.createPost(post_origin="inbox", user=username, content={"h": "Notification", "p": "You have been given ownership of the group chat '{0}'!".format(chatdata["nickname"])})

        # Tell client user was removed
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)

    def get_inbox(self, client, val, listener_detected, listener_id):
        if not self.supporter.isAuthenticated(client):
            # Not authenticated
            return self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
        elif not (type(val) == dict):
            # Bad datatype
            return self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)

        # Set page number
        if ("page" in val) and (type(val["page"]) == int):
            page = val["page"]
        else:
            page = 1

        # Get inbox messages
        inbox_index = self.filesystem.find_items("posts", {"post_origin": "inbox", "u": {"$in": ["Server", client]}, "isDeleted": False}, sort="t.e", truncate=True, page=page)
        print(inbox_index)
        payload = {
            "mode": "inbox",
            "payload": inbox_index
        }

        # Relay payload to user
        self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)

        # Tell user payload was sent
        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
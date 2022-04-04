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
        self.log("Meower initialized!")
    
    # Some Meower-library specific utilities needed
    
    def getIndex(self, location="/Storage/Categories/Home/",  truncate=False, convert=False, mode=1, page=1, query="", noCheck=False):
        if mode == 1:
            result, ls = self.filesystem.get_directory(location + "Indexes/")
        elif mode == 2:
            result, ls = self.filesystem.get_directory(location)
        elif mode == 3:
            result = True
        if result:
            if mode == 1:
                today = self.supporter.timestamp(5)
                if today in ls:
                    result, payload = self.filesystem.load_file((location + "Indexes/") + today)
                    if result:
                        payload = payload["index"]
                        
                        if truncate:
                            # Truncate to 25 items.
                            payload = payload[(len(payload)-25):len(payload)]
                    
                        if convert:
                            #convert list to format that meower can use
                            tmp1 = ""
                            for item in payload:
                                tmp1 = str(tmp1 + item + ";")
                            return 2, tmp1
                        else:
                            return 2, payload
                else:
                    result = self.filesystem.create_file((location + "Indexes/"), today, {"index":[]})
                    if result:
                        return 1, ";"
                    else:
                        return 0, None
            elif mode == 2:
                query_get = []
                
                if not noCheck:
                    for file in ls:
                        if file.split("-")[0] == query:
                            query_get.append(file)
                else:
                    for file in ls:
                        query_get.append(file)
                query_get.reverse()
               
                # Get number of pages
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
                
                query_convert = ""
                for item in query_return:
                    query_convert = str(query_convert + str(item) + ";")
                
                query_return = {
                    "query": query,
                    "index": query_convert,
                    "page#": page,
                    "pages": pages
                }
                
                return True, query_return
            elif mode == 3:
                result, payload = self.filesystem.load_file(location + query)
                if result:
                    ls = payload["index"]
                    
                    query_get = []
                    
                    if not noCheck:
                        for file in ls:
                            if file.split("-")[0] == query:
                                query_get.append(file)
                    else:
                        for file in ls:
                            query_get.append(file)
                    query_get.reverse()
                   
                    # Get number of pages
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
                    
                    if convert:
                        query_convert = ""
                        for item in query_return:
                            query_convert = str(query_convert + str(item) + ";")
                    else:
                        query_convert = query_return
                    
                    query_return = {
                        "query": query,
                        "index": query_convert,
                        "page#": page,
                        "pages": pages
                    }
                    
                    return True, query_return
                else:
                    result = self.filesystem.create_file(location, query, {"index":[]})
                    if result:
                        return 1, {
                            "query": query,
                            "index": [],
                            "page#": 1,
                            "pages": 0
                        }
                    else:
                        return 0, None
        else:
            if mode == 1:
                return 0, None
            elif mode == 2:
                return False, None
            elif mode == 3:
                return False, None
    
    def appendToIndex(self, location="/Storage/Categories/Home/", toAdd="", mode=1, fileid=""):
        if mode == 1:
            result, ls = self.filesystem.get_directory(location + "Indexes/")
        else:
            result, ls = self.filesystem.get_directory(location)
        if result:
            if mode == 1:
                today = self.supporter.timestamp(5)
                if today in ls:
                    result, payload = self.filesystem.load_file((location + "Indexes/") + today)
                    if result:
                        self.log("Appending {0} to indexer at {1}".format(toAdd, location))
                        payload["index"].append(toAdd)
                        return self.filesystem.write_file((location + "Indexes/"), today, payload)
                else:
                    return self.filesystem.create_file((location + "Indexes/"), today, {"index":[toAdd]})
            elif mode == 2:
                if fileid in ls:
                    result, payload = self.filesystem.load_file((location) + fileid)
                    if result:
                        self.log("Appending {0} to indexer at {1}".format(toAdd, location))
                        payload["index"].append(toAdd)
                        return self.filesystem.write_file((location), fileid, payload)
                else:
                    return self.filesystem.create_file((location), fileid, {"index":[toAdd]})
        else:
            return False
     
    def removeFromIndex(self, location="/Storage/Categories/Home/", toRemove=""):
        result, ls = self.filesystem.get_directory(location + "Indexes/")
        if result:
            today = self.supporter.timestamp(5)
            if today in ls:
                result, payload = self.filesystem.load_file((location + "Indexes/") + today)
                if result:
                    if toRemove in payload["index"]:
                        self.log("Removing {0} from indexer at {1}".format(toRemove, location))
                        payload["index"].remove(toRemove)
                        return self.filesystem.write_file((location + "Indexes/"), today, payload)
                    else:
                        return True
            else:
                return self.filesystem.create_file((location + "Indexes/"), today, {"index":[]})
        else:
            return False
    
    def clearIndex(self, location="/Storage/Categories/Home/"):
        result, ls = self.filesystem.get_directory(location + "Indexes/")
        if result:
            today = self.supporter.timestamp(5)
            if today in ls:
                result, payload = self.filesystem.load_file((location + "Indexes/") + today)
                if result:
                    self.log("Removing all from indexer at {0}".format(location))
                    payload["index"] = []
                    return self.filesystem.write_file((location + "Indexes/"), today, payload)
            else:
                return self.filesystem.create_file((location + "Indexes/"), today, {"index":[]})
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
            result, payload = self.filesystem.load_file("/Config/supported_versions.json")
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
                                if FileCheck and FileRead:
                                    if not Banned:
                                        FileCheck, FileRead, ValidAuth = self.accounts.authenticate(username, password)
                                        if FileCheck and FileRead:
                                            if ValidAuth:
                                                self.supporter.kickBadUsers(username) # Kick bad clients missusing the username
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
                                        # Account banned
                                        self.returnCode(client = client, code = "Banned", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    if ((not FileCheck) and FileRead):
                                        # Account does not exist
                                        self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
                                    self.supporter.autoID(client, username) # If the client is JS-based then give them an AutoID
                                    self.supporter.setAuthenticatedState(client, True) # Make the server know that the client is authed
                                    
                                    # Return info to sender
                                    payload = {
                                        "mode": "auth",
                                        "payload": ""
                                    }
                                    
                                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                    
                                    # Tell the client it is authenticated
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    
                                    # Log peak users
                                    self.supporter.log_peak_users()
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
    
    def get_home(self, client, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            try:
                status, payload = self.getIndex(location="/Storage/Categories/Home/", truncate=True, convert=True)
                
                if status != 0:
                    payload = {
                        "mode": "home",
                        "payload": payload
                    }
                self.log("{0} getting home index".format(client))
                
                if status == 0: # Home error
                    self.log("Error while generating homepage")
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                else: # Home was generated
                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                
                #result = self.appendToIndex(location="/Storage/Categories/Home/", toAdd="test")
                #result = self.removeFromIndex(location="/Storage/Categories/Home/", toRemove="test")
            except:
                self.log("{0}".format(self.errorhandler()))
                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def post_home(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 360:
                    if self.supporter.check_for_spam(client):
                        
                        # Generate a Post ID
                        post_id = str(client) + "-" + str(self.supporter.timestamp(3))
                        
                        #Filter the post through better-profanity
                        post = self.supporter.wordfilter(val)
                        
                        # Create post format
                        post_w_metadata = self.supporter.timestamp(1).copy()
                        post_w_metadata["p"] = str(post)
                        post_w_metadata["post_origin"] = "home"
                        post_w_metadata["isDeleted"] = False
                        post_w_metadata["u"] = str(client)
                        post_w_metadata["post_id"] = str(post_id)
                        
                        # Store post in filesystem
                        result = self.filesystem.create_file("/Storage/Categories/Home/Messages/", str(post_id), post_w_metadata)
                        if result:
                            self.log("{0} posting home message {1}".format(client, post_id))
                            # Add post to homepage index
                            result = self.appendToIndex(location="/Storage/Categories/Home/", toAdd=str(post_id))
                            if result:
                                # Relay post to clients
                                    
                                post_w_metadata_2 = post_w_metadata.copy()
                                post_w_metadata_2["mode"] = 1
                                
                                self.sendPacket({"cmd": "direct", "val": post_w_metadata_2})
                                
                                # Tell client message was sent
                                self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                
                                self.supporter.ratelimit(client)
                            else:
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
                status, payload = self.filesystem.get_directory("/Storage/Categories/Home/Messages/")
                if status:
                    if val in payload:
                        result, payload = self.filesystem.load_file("/Storage/Categories/Home/Messages/{0}".format(val))
                        if result:
                            if ("isDeleted" in payload) and (payload["isDeleted"]):
                                payload = {
                                    "mode": "post",
                                    "isDeleted": True
                                }
                            
                            else:
                                payload = {
                                    "mode": "post",
                                    "payload": payload,
                                    "isDeleted": False
                                }
                            
                            self.log("{0} getting home post {1}".format(client, val))
                            # Relay post to client
                            self.sendPacket({"cmd": "direct", "val": payload, "id": client})
                            
                            # Tell client message was sent
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Post not found
                        self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
                if ("query" in val):
                    if (type(val["query"]) == str): # ("page" in val) (type(val["page"]) == int)
                        if ("page" in val) and (type(val["page"]) == int):
                            try:
                                status, payload = self.getIndex(location="/Storage/Categories/Home/Messages/", mode=2, page=val["page"], query=val["query"])
                                if status:
                                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            except:
                                self.log("{0}".format(self.errorhandler()))
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            try:
                                status, payload = self.getIndex(location="/Storage/Categories/Home/Messages/", mode=2, page=1, query=val["query"])
                                if status:
                                    self.sendPacket({"cmd": "direct", "val": payload, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            except:
                                self.log("{0}".format(self.errorhandler()))
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
    
    # Moderator features
    
    def clear_home(self, client, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 1:
                    result = self.clearIndex(location="/Storage/Categories/Home/")
                    if result:
                        # Return to the client it's data
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def block(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 2:
                    result, payload = self.filesystem.load_file("/Jail/IPBanlist.json")
                    if result:
                        if type(val) == str:
                            if not val in payload["wildcard"]:
                                payload["wildcard"].append(val)
                                result = self.filesystem.write_file("/Jail/", "IPBanlist.json", payload)
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
                    result, payload = self.filesystem.load_file("/Jail/IPBanlist.json")
                    if result:
                        if type(val) == str:
                            if val in payload["wildcard"]:
                                payload["wildcard"].remove(val)
                                result = self.filesystem.write_file("/Jail/", "IPBanlist.json", payload)
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
                        if val in self.cl.getUsernames():
                            self.sendPacket({"cmd": "direct", "val": {"username": str(val), "ip": str(self.cl.getIPofUsername(val))}, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # User not found
                            self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
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
                            
                            FileCheck, FileRead, Payload = self.accounts.get_account(val, False, True)
                            if FileCheck and FileRead:
                                self.sendPacket({"cmd": "direct", "val": {"username": str(val), "payload": Payload}, "id": client}, listener_detected = listener_detected, listener_id = listener_id)
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
                if ((not FileCheck) and FileRead):
                    # Account not found
                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
                        result, payload = self.filesystem.load_file("/Jail/IPBanlist.json")
                        if result:
                            if val in self.cl.getUsernames():
                                userIP = self.cl.getIPofUsername(val)
                                if not str(val) in payload["users"]:
                                    payload["users"][str(val)] = str(userIP)
                                    
                                    if not str(userIP) in payload["wildcard"]:
                                        payload["wildcard"].append(str(userIP))
                                    
                                    result = self.filesystem.write_file("/Jail/", "IPBanlist.json", payload)
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
                                # User not found
                                self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
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
                        result, payload = self.filesystem.load_file("/Jail/IPBanlist.json")
                        if result:
                            if val in payload["users"]:
                                userIP = payload["users"][val]
                                if str(val) in payload["users"]:
                                    del payload["users"][str(val)]
                                    
                                    if str(userIP) in payload["wildcard"]:
                                        payload["wildcard"].remove(str(userIP))
                                    
                                    result = self.filesystem.write_file("/Jail/", "IPBanlist.json", payload)
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
            FileCheck, FileRead, accountData = self.accounts.get_account(client, True, True)
            if FileCheck and FileRead:
                if accountData["lvl"] >= 1:
                    if type(val) == str:
                        status, payload = self.filesystem.get_directory("/Storage/Categories/Home/Messages/")
                        if status:
                            if val in payload:
                                result, payload = self.filesystem.load_file("/Storage/Categories/Home/Messages/{0}".format(val))
                                if result:
                                    payload["isDeleted"] = True
                                    result = self.filesystem.write_file("/Storage/Categories/Home/Messages/", str(val), payload)
                                    if result:
                                        result = self.removeFromIndex(location="/Storage/Categories/Home/", toRemove=val)
                                        if result:
                                            self.log("{0} deleting home post {1}".format(client, val))
                                            # Relay post to clients
                                            self.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": val}})
                                            
                                            # Return to the client it's data
                                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                        else:
                                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Post not found
                                self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
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
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def create_chat(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                if not len(val) > 20:
                    
                    # Create user's chat directory if they haven't created a chat before
                    result = self.filesystem.create_directory("/Storage/Chats/UserIndexes/{0}".format(client))
                    
                    if not self.supporter.checkForBadCharsUsername(val):
                        if result:
                            result, ls = self.filesystem.get_directory("/Storage/Chats/UserIndexes/{0}/".format(client))
                            if result:
                                if not val in ls:
                                    # Create chat ID in root index of chats
                                    chat_uuid = str(uuid.uuid4()) # Generate a UUID for the chat
                                    self.log("New chat: {0} UUID: {1}".format(val, chat_uuid))
                                    result = self.filesystem.create_file("/Storage/Chats/Indexes/", "{0}".format(chat_uuid), {
                                        "index": [],
                                        "owner": client,
                                        "nickname": val
                                        }
                                    )
                                    
                                    # Create reference indexer for user
                                    result2 = self.filesystem.create_file("/Storage/Chats/UserIndexes/{0}/".format(client), "{0}".format(val), {
                                        "chat_uuid": chat_uuid
                                        }
                                    )
                                    
                                    if result and result2:
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    else:   
                                        # Some other error, raise an internal error.
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Chat exists
                                    self.returnCode(client = client, code = "ChatExists", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Some other error, raise an internal error.
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
                if not len(val) > 20:
                    
                    # Create user's chat directory if they haven't created a chat before
                    result = self.filesystem.create_directory("/Storage/Chats/UserIndexes/{0}".format(client))
                    
                    if not self.supporter.checkForBadCharsUsername(val):
                        if result:
                            result, ls = self.filesystem.get_directory("/Storage/Chats/UserIndexes/{0}/".format(client))
                            if result:
                                if val in ls:
                                    # Delete reference indexer for user
                                    result = self.filesystem.delete_file("/Storage/Chats/UserIndexes/{0}/".format(client), "{0}".format(val))
                                    
                                    if result:
                                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    else:   
                                        # Some other error, raise an internal error.
                                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Chat does not exist
                                    self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Some other error, raise an internal error.
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def get_chat_list(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            result, ls = self.filesystem.get_directory("/Storage/Chats/UserIndexes/")
            if result:
                if client in ls:
                    if type(val) == dict:
                        if ("page" in val) and (type(val["page"]) == int):
                            page = val["page"]
                        else:
                            page = 1
                        result, payload = self.getIndex(
                            "/Storage/Chats/UserIndexes/{0}/".format(client),
                            truncate = True,
                            convert = True,
                            mode = 2,
                            page = page, 
                            noCheck = True
                        )
                        
                        if result:
                            self.sendPacket({"cmd": "direct", "val": payload, "id": client})
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            # Some other error, raise an internal error.
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Bad datatype
                        self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Create user's chat directory if they haven't created a chat before
                    result = self.filesystem.create_directory("/Storage/Chats/UserIndexes/{0}".format(client))
                    if result:
                        self.log("Creating user chat index for {0}".format(client))
                        self.sendPacket({"cmd": "direct", "val": {
                            "query": "",
                            "index": ";",
                            "page#": 1,
                            "pages": 1
                        }, "id": client})
                        self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Some other error, raise an internal error.
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Some other error, raise an internal error.
                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
    def get_chat_data(self, client, val, listener_detected, listener_id):
        # Check if the client is already authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                result, ls = self.filesystem.get_directory("/Storage/Chats/UserIndexes/")
                if result:
                    if client in ls:
                        if type(val) == str:
                            result, payload = self.filesystem.load_file("/Storage/Chats/UserIndexes/{0}/{1}".format(client, val))
                            if result:
                                chat_uuid = payload["chat_uuid"] # Get the Chat UUID
                                
                                # Read the chat current index for downloading
                                result, payload = self.getIndex(
                                    location = "/Storage/Chats/Indexes/",
                                    query = chat_uuid,
                                    truncate = True,
                                    convert = True,
                                    mode = 3,
                                    page = 1, 
                                    noCheck = True
                                )
                                
                                if result:
                                    del payload["query"]
                                    payload["chat_uuid"] = chat_uuid
                                    
                                    self.sendPacket({"cmd": "direct", "val": payload, "id": client})
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
                        # Some other error, raise an internal error.
                        self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    # Some other error, raise an internal error.
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
            else:
                # Bad datatype
                self.returnCode(client = client, code = "Datatype", listener_detected = listener_detected, listener_id = listener_id)
        else:
            # Not authenticated
            self.returnCode(client = client, code = "Refused", listener_detected = listener_detected, listener_id = listener_id)
    
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
                
                if (not len(post) > 100) and (not len(chatid) > 50):
                    if self.supporter.check_for_spam(client):
                        
                        # Generate a Post ID
                        post_id = str(client) + "-" + str(self.supporter.timestamp(3))
                        
                        #Filter the post through better-profanity
                        post = self.supporter.wordfilter(post)
                        
                        # Create post format
                        post_w_metadata = self.supporter.timestamp(1).copy()
                        post_w_metadata["p"] = str(post)
                        post_w_metadata["u"] = str(client)
                        post_w_metadata["chatid"] = str(chatid)
                        post_w_metadata["post_id"] = str(post_id)
                        post_w_metadata["state"] = 2
                        
                        if chatid == "livechat":
                            self.log("{0} posting {1} message".format(client, chatid))
                            
                            self.sendPacket({"cmd": "direct", "val": post_w_metadata})
                            
                            # Tell client message was sent
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                            self.supporter.ratelimit(client)
                        else:
                            # Store post in filesystem
                            result = self.filesystem.create_file("/Storage/Chats/Messages/", str(post_id), post_w_metadata)
                            if result:
                                self.log("{0} posting chat message {1}".format(client, post_id))
                                # Add post to chat index
                                result = self.appendToIndex(location="/Storage/Chats/Indexes/", toAdd=str(post_id), fileid=str(chatid), mode=2)
                                if result:
                                    self.sendPacket({"cmd": "direct", "val": post_w_metadata})
                            
                                    # Tell client message was sent
                                    self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                    self.supporter.ratelimit(client)
                                else:
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
    
    def get_chat_post(self, client, val, listener_detected, listener_id):
        # Check if the client is authenticated
        if self.supporter.isAuthenticated(client):
            if type(val) == str:
                status, payload = self.filesystem.get_directory("/Storage/Chats/Messages/")
                if status:
                    if val in payload:
                        result, payload = self.filesystem.load_file("/Storage/Chats/Messages/{0}".format(val))
                        if result:
                            if ("isDeleted" in payload) and (payload["isDeleted"]):
                                payload = {
                                    "mode": "post",
                                    "isDeleted": True
                                }
                            
                            else:
                                payload = {
                                    "mode": "post",
                                    "payload": payload,
                                    "isDeleted": False
                                }
                            
                            self.log("{0} getting chat post {1}".format(client, val))
                            # Relay post to client
                            self.sendPacket({"cmd": "direct", "val": payload, "id": client})
                            
                            # Tell client message was sent
                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                        else:
                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                    else:
                        # Post not found
                        self.returnCode(client = client, code = "IDNotFound", listener_detected = listener_detected, listener_id = listener_id)
                else:
                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
                if (("username" in val) and (type(val["username"]) == str)) and (("chat_id" in val) and (type(val["chat_id"]) == str)):
                    username = val["username"]
                    chat_uuid = val["chat_id"]
                    
                    # Read chat UUID's nickname
                    result, payload = self.filesystem.load_file("/Storage/Chats/Indexes/{0}".format(chat_uuid))
                    
                    if result:
                        chat_nickname = payload["nickname"]
                        if username in self.cl.getUsernames():
                            # Create user's chat directory if they haven't created a chat before
                            result = self.filesystem.create_directory("/Storage/Chats/UserIndexes/{0}".format(username))
                            if result:
                                result, ls = self.filesystem.get_directory("/Storage/Chats/UserIndexes/{0}/".format(username))
                                if result:
                                    if not val in ls:
                                        self.log("Adding to chat: {0} UUID: {1}".format(username, chat_uuid))
                                        
                                        # Create reference indexer for user
                                        result2 = self.filesystem.create_file("/Storage/Chats/UserIndexes/{0}/".format(username), "{0}".format(chat_nickname), {
                                            "chat_uuid": chat_uuid
                                            }
                                        )
                                        
                                        if result and result2:
                                            self.returnCode(client = client, code = "OK", listener_detected = listener_detected, listener_id = listener_id)
                                        else:   
                                            # Some other error, raise an internal error.
                                            self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                                    else:
                                        # Chat exists
                                        self.returnCode(client = client, code = "ChatExists", listener_detected = listener_detected, listener_id = listener_id)
                                else:
                                    # Some other error, raise an internal error.
                                    self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
                            else:
                                # Some other error, raise an internal error.
                                self.returnCode(client = client, code = "InternalServerError", listener_detected = listener_detected, listener_id = listener_id)
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
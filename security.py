import bcrypt
from uuid import uuid4

"""
Meower Security Module
This module provides account management and authentication services.
"""

class Security:
    def __init__(self, files, supporter, logger, errorhandler):
        self.bc = bcrypt
        self.supporter = supporter
        self.files = files
        self.log = logger
        self.errorhandler = errorhandler
        self.log("Security initialized!")
    
    def create_account(self, username, password, strength=12):
    
        """
        Returns 2 booleans.
        
        | FileCheck | FileWrite | Definiton
        |---------|----------|-----------------
        |  True  |   True   | Account created
        |  True  |   False  | Account creation error
        |  False |   True   | Account already exists
        |  False |   False  | Exception
        """
        
        if (type(password) == str) and (type(username) == str):
            if not self.account_exists(str(username), ignore_case=True):
                self.log("Creating account: {0}".format(username))
                pswd_bytes = bytes(password, "utf-8") # Convert password to bytes
                hashed_pw = self.bc.hashpw(pswd_bytes, self.bc.gensalt(strength)) # Hash and salt the password
                result = self.files.create_item("usersv0", str(username), { # Default account data
                        "lower_username": username.lower(),
                        "uuid": str(uuid4()),
                        "unread_inbox": False,
                        "theme": "orange",
                        "mode": True,
                        "sfx": True,
                        "debug": False,
                        "bgm": True,
                        "bgm_song": 2,
                        "layout": "new",
                        "pfp_data": 1,
                        "quote": "",
                        "email": "",
                        "pswd": hashed_pw.decode(),
                        "tokens": [],
                        "lvl": 0,
                        "banned": False,
                        "last_ip": None
                    }
                )
                return True, result
            else:
                self.log("Not creating account {0}: Account already exists".format(username))
                return False, True
        else:
            self.log("Error on generate_account: Expected str for username and password, got {0} for username and {1} for password".format(type(username), type(password)))
            return False, False
    
    def get_account(self, username, omitSensitive=False, isClient=False):
        """
        Returns 2 booleans, plus a payload.
        
        | FileCheck | FileRead | Definiton
        |---------|----------|-----------------
        |  True   |   True   | Account exists and read 
        |  True   |   False  | Account exists, read error
        |  False  |   True   | Account does not exist
        |  False  |   False  | Exception
        """
        
        if type(username) == str:
            if self.files.does_item_exist("usersv0", str(username)):
                self.log("Reading account: {0}".format(username))
                result, accountData = self.files.load_item("usersv0", str(username))
                
                if omitSensitive: # Purge sensitive data and remove user settings
                    for sensitive in [
                        "unread_inbox",
                        "theme",
                        "mode",
                        "sfx",
                        "debug",
                        "bgm",
                        "bgm_song",
                        "layout",
                        "email",
                        "pswd",
                        "tokens",
                        "last_ip"
                    ]:
                        if sensitive in accountData:
                            del accountData[sensitive]
                
                if isClient:
                    if "pswd" in accountData:
                        del accountData["pswd"]
                    if "tokens" in accountData:
                        del accountData["tokens"]
                    if "last_ip" in accountData:
                        del accountData["last_ip"]
                
                return True, result, accountData
            else:
                return False, True, None
        else:
            self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
            return False, False, None
    
    def authenticate(self, username, password): 
        """
        Returns 3 booleans.
        
        | FileCheck | FileRead | ValidAuth | Definiton
        |---------|----------|----------|-----------------
        |  True   |   True   |  True    | Account exists, read OK, authentication valid
        |  True   |   True   |  False   | Account exists, read OK, authentication invalid
        |  True   |   False  |  False   | Account exists, read error
        |  False  |   True   |  False   | Account does not exist
        |  False  |   False  |  False   | Exception
        """
        
        if type(username) == str:
            if self.files.does_item_exist("usersv0", str(username)):
                self.log("Authenticating account: {0}".format(username))
                FileRead, accountData = self.files.load_item("usersv0", str(username))
                if FileRead:
                    if type(accountData) == dict:
                        if accountData["banned"] == True:
                            return True, True, False, True
                        if password in accountData["tokens"]:
                            self.log("Authenticating {0}: True".format(username))
                            accountData["tokens"].remove(password)
                            self.update_setting(username, {"tokens": accountData["tokens"]}, forceUpdate=True)
                            return True, True, True, False
                        else:
                            hashed_pw = accountData["pswd"]
                            pswd_bytes = bytes(password, "utf-8")
                            hashed_pw_bytes = bytes(hashed_pw, "utf-8")
                            try:
                                result = self.bc.checkpw(pswd_bytes, hashed_pw_bytes)
                                self.log("Authenticating {0}: {1}".format(username, result))
                                return True, True, result, False
                            except Exception as e:
                                self.log("Error on authenticate: {0}".format(e))
                                return True, True, False, False
                    else:
                        self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
                        return False, False, False, False
                else:
                    return True, False, False, False
            else:
                return False, True, False, False
        else:
            self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
            return False, False, False, False
    
    def change_password(self, username, newpassword, strength=12):
        """
        Returns 3 booleans.
        
        | FileCheck | FileRead | FileWrite | Definiton
        |---------|----------|----------|-----------------
        |  True   |   True   |  True    | Account exists, read OK, password changed
        |  True   |   False  |  False   | Account exists, read error
        |  False  |   True   |  False   | Account does not exist
        |  False  |   False  |  False   | Exception
        """
        
        if (type(username) == str) and (type(newpassword) == str):
            if self.files.does_item_exist("usersv0", str(username)):
                self.log("Changing {0} password".format(username))
                result, accountData = self.files.load_item("usersv0", str(username))
                if result:
                    try:
                        pswd_bytes = bytes(newpassword, "utf-8") # Convert password to bytes
                        hashed_pw = self.bc.hashpw(pswd_bytes, self.bc.gensalt(strength)) # Hash and salt the password
                        
                        accountData["pswd"] = hashed_pw.decode()
                        
                        result = self.files.write_item("usersv0", str(username), accountData)
                        self.log("Change {0} password: {1}".format(username, result))
                        return True, True, result
                    except Exception as e:
                        self.log("Error on authenticate: {0}".format(e))
                        return True, True, False
                else:
                    return True, False, False
            else:
                return False, True, False
        else:
            self.log("Error on get_account: Expected str for username, oldpassword and newpassword, got {0} for username and {1} for newpassword".format(type(username), type(newpassword)))
            return False, False, False
    
    def account_exists(self, username, ignore_case=False):
        if type(username) == str:
            if ignore_case:
                payload = self.files.find_items("usersv0", {"lower_username": str(username).lower()})
                if len(payload) == 0:
                    return False
                else:
                    return True
            else:
                return self.files.does_item_exist("usersv0", str(username))
        else:
            self.log("Error on account_exists: Expected str for username, got {0}".format(type(username)))
            return False
    
    def is_account_banned(self, username):
        """
        Returns 2 booleans, plus a payload.
        
        | FileCheck | FileRead | Banned | Definiton
        |---------|----------|----------|-----------------
        |  True   |   True   |   True   | Account exists and read, account banned
        |  True   |   True   |   False  | Account exists and read, account NOT banned
        |  True   |   False  |   False  | Account exists, read error
        |  False  |   True   |   False  | Account does not exist
        |  False  |   False  |   False  |  Exception
        """
        
        if type(username) == str:
            if self.files.does_item_exist("usersv0", str(username)):
                self.log("Reading account: {0}".format(username))
                result, accountData = self.files.load_item("usersv0", str(username))
                return True, result, accountData["banned"]
            else:
                return False, True, None
        else:
            self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
            return False, False, None
    
    def update_setting(self, username, newdata, forceUpdate=False):
        """
        Returns 3 booleans.
        
        | FileCheck | FileRead | FileWrite | Definiton
        |---------|----------|----------|-----------------
        |  True   |   True   |  True    | Account exists, read OK, settings changed
        |  True   |   True   |  False   | Account exists, read OK, settings write error
        |  True   |   False  |  False   | Account exists, read error
        |  False  |   True   |  False   | Account does not exist
        |  False  |   False  |  False   | Exception
        """
        
        if (type(username) == str) and (type(newdata) == dict):
            if self.files.does_item_exist("usersv0", str(username)):
                self.log("Updating account settings: {0}".format(username))
                result, accountData = self.files.load_item("usersv0", str(username))
                if result:
                    for key, value in newdata.items():
                        if key in accountData.keys():
                            if forceUpdate:
                                accountData[key] = value
                            else:
                                if key not in ["lvl", "pswd", "banned", "email", "last_ip", "lower_username", "uuid", "tokens", "created"]:
                                    if key in accountData.keys():
                                        if ((type(value) == str) and (len(value) <= 360)) or ((type(value) == int) and (len(str(value)) <= 360)) or ((type(value) == float) and (len(str(value)) <= 360)) or (type(value) == bool) or (type(value) == None):
                                            if type(value) == str:
                                                accountData[key] = self.supporter.wordfilter(value)
                                            else:
                                                accountData[key] = value
                                else:
                                    self.log("Blocking attempt to modify secure key {0}".format(key))
                    
                    result = self.files.write_item("usersv0", str(username), accountData)
                    self.log("Updating {0} account settings: {1}".format(username, result))
                    return True, True, result
                else:
                    return True, False, False
            else:
                return False, True, False
        else:
            self.log("Error on get_account: Expected str for username and dict for newdata, got {0} for username and {1} for newdata".format(type(username), type(newdata)))
            return False, False, False

    def delete_account(self, username):
        """
        Returns 2 booleans.
        
        | FileCheck | FileRead | Definiton
        |---------|----------|-----------------
        |  True   |   True   | Account exists and read 
        |  True   |   False  | Account exists, read error
        |  False  |   True   | Account does not exist
        |  False  |   False  | Exception
        """

        if type(username) == str:
            if self.files.does_item_exist("usersv0", str(username)):
                self.log("Deleting account: {0}".format(username))
                # Delete userdata
                self.files.delete_item("usersv0", str(username))
                # Delete group chats
                self.files.db["chats"].delete_many({"owner": username})
                chat_index = self.files.db["chats"].find({"members": {"$all": [username]}})
                for chat in chat_index:
                    chat["members"].remove(username)
                    self.files.write_item("chats", chat["_id"], chat)
                # Delete posts
                self.files.db["posts"].delete_many({"u": username})
                # Delete netlog data
                netlog_index = self.files.db["netlog"].find({"users": {"$all": [username]}})
                for ip in netlog_index:
                    ip["users"].remove(username)
                    if len(ip["users"]) == 0:
                        self.files.delete_item("netlog", ip["_id"])
                    else:
                        if ip["last_user"] == username:
                            ip["last_user"] = ip["users"][(len(ip["users"])-1)]
                        self.files.write_item("netlog", ip["_id"], ip)
                return True, True, True
            else:
                return False, False
        else:
            self.log("Error on delete_account: Expected str for username, got {0} for username".format(type(username)))
            return False, False
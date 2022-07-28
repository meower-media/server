import bcrypt

"""
Meower Security Module
This module provides account management and authentication services.
"""

class Security:
    def __init__(self, files, logger, errorhandler):
        self.bc = bcrypt
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
                        "theme",
                        "mode",
                        "sfx",
                        "debug",
                        "bgm",
                        "bgm_song",
                        "layout",
                        "email",
                        "pswd",
                        "last_ip"
                    ]:
                        del accountData[sensitive]
                
                if isClient:
                    if "pswd" in accountData:
                        del accountData["pswd"]
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
                result, accountData = self.files.load_item("usersv0", str(username))
                if result:
                    if type(accountData) == dict:
                        hashed_pw = accountData["pswd"]
                        pswd_bytes = bytes(password, "utf-8")
                        hashed_pw_bytes = bytes(hashed_pw, "utf-8")
                        try:
                            result = self.bc.checkpw(pswd_bytes, hashed_pw_bytes)
                            self.log("Authenticating {0}: {1}".format(username, result))
                            return True, True, result
                        except Exception as e:
                            self.log("Error on authenticate: {0}".format(e))
                            return True, True, False
                    else:
                        self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
                        return False, False, False
                else:
                    return True, False, False
            else:
                return False, True, False
        else:
            self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
            return False, False, False
    
    def change_password(self, username, oldpassword, newpassword, strength=12):
        """
        Returns 3 booleans.
        
        | FileCheck | FileRead | FileWrite | Definiton
        |---------|----------|----------|-----------------
        |  True   |   True   |  True    | Account exists, read OK, password changed
        |  True   |   True   |  False   | Account exists, read OK, password not changed (invalid credentials)
        |  True   |   False  |  False   | Account exists, read error
        |  False  |   True   |  False   | Account does not exist
        |  False  |   False  |  False   | Exception
        """
        
        if (type(username) == str) and (type(oldpassword) == str) and (type(newpassword) == str):
            if self.files.does_item_exist("usersv0", str(username)):
                self.log("Changing {0} password".format(username))
                result, accountData = self.files.load_item("usersv0", str(username))
                if result:
                    hashed_pw = accountData["pswd"]
                    pswd_bytes = bytes(oldpassword, "utf-8")
                    hashed_pw_bytes = bytes(hashed_pw, "utf-8")
                    try:
                        result = self.bc.checkpw(pswd_bytes, hashed_pw_bytes)
                        if result:
                            pswd_bytes = bytes(newpassword, "utf-8") # Convert password to bytes
                            hashed_pw = self.bc.hashpw(pswd_bytes, self.bc.gensalt(strength)) # Hash and salt the password
                            
                            accountData["pswd"] = hashed_pw.decode()
                            
                            result = self.files.write_item("usersv0", str(username), accountData)
                            self.log("Change {0} password: {1}".format(username, result))
                            return True, True, result
                        else:
                            self.log("Change {0} password: invalid password".format(username))
                            return True, True, False 
                    except Exception as e:
                        self.log("Error on authenticate: {0}".format(e))
                        return True, True, False
                else:
                    return True, False, False
            else:
                return False, True, False
        else:
            self.log("Error on get_account: Expected str for username, oldpassword and newpassword, got {0} for username, {1} for oldpassword, and {2} for newpassword".format(type(username), type(oldpassword), type(newpassword)))
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
                        if forceUpdate:
                            if key in accountData.keys():
                                accountData[key] = value
                        else:
                            if not key in ["lvl", "pswd", "banned", "email", "last_ip", "lower_username"]:
                                if key in accountData.keys():
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

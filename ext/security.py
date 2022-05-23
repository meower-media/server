import bcrypt
import time

"""
Meower Security Module
This module provides account management and authentication services.
"""

class Security:
    def __init__(self, meower):
        self.files = meower.files
        self.log = meower.supporter.log
        self.errorhandler = meower.supporter.full_stack
        self.log("Security initialized!")
    
    class Config:
        def __init__(self, username):
            file_check, file_read, userdata = self.files.load_item("usersv0", username)
    
            if file_check and file_read:
                self.theme = userdata["theme"]
                self.mode = userdata["mode"]
                self.sfx = userdata["sfx"]
                self.debug = userdata["debug"]
                self.bgm = userdata["bgm"]
                self.bgm_song = userdata["bgm_song"]
                self.pfp_data = userdata["pfp_data"]
                self.quote = userdata["quote"]
            else:
                self.theme = "orange"
                self.mode = True
                self.sfx = True
                self.debug = False
                self.bgm = True
                self.bgm_song = 2
                self.pfp_data = 1
                self.quote = ""

            self.json = {
                "theme": self.theme,
                "mode": self.mode,
                "sfx": self.sfx,
                "debug": self.debug,
                "bgm": self.bgm,
                "bgm_song": self.bgm_song,
                "pfp_data": self.pfp_data,
                "quote": self.quote
            }

    class User:
        def __init__(self, username):
            file_check, file_read, userdata = self.files.load_item("usersv0", username)
            if file_check and file_read:
                self.username = userdata["_id"]
                self.lower_username = userdata["lower_username"]
                self.config = {
                    "theme": userdata["theme"],
                    "mode": userdata["mode"],
                    "sfx": userdata["sfx"],
                    "debug": userdata["debug"],
                    "bgm": userdata["bgm"],
                    "bgm_song": userdata["bgm_song"],
                    "pfp_data": userdata["pfp_data"],
                    "quote": userdata["quote"]
                }

    def account_exists(self, username, ignore_case=False):
        if not (type(username) == str):
            self.log("Error on account_exists: Expected str for username, got {0}".format(type(username)))
            return False
        if ignore_case:
            payload = self.files.find_items("usersv0", {"lower_username": str(username).lower()})
            if len(payload) == 0:
                return False
            else:
                return True
        else:
            return self.files.does_item_exist("usersv0", str(username))   

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
        
        if not ((type(username) == str) and (type(password) == str)):
            self.log("Error on generate_account: Expected str for username and password, got {0} for username and {1} for password".format(type(username), type(password)))
            return False, False
        if self.account_exists(str(username), ignore_case=True):
            self.log("Not creating account {0}: Account already exists".format(username))
            return False, True
        
        self.log("Creating account: {0}".format(username))
        pswd_bytes = bytes(password, "utf-8") # Convert password to bytes
        hashed_pw = bcrypt.hashpw(pswd_bytes, bcrypt.gensalt(strength)) # Hash and salt the password
        FileWrite = self.files.create_item("usersv0", username, { # Default account data
                "lower_username": username.lower(),
                "theme": "orange",
                "mode": True,
                "sfx": True,
                "debug": False,
                "bgm": True,
                "bgm_song": 2,
                "layout": "new", # Remove once beta 6 happens
                "pfp_data": 1,
                "quote": "",
                "email": "",
                "pswd": hashed_pw.decode(),
                "lvl": 0,
                "flags": {
                    "dormant": False,
                    "locked_until": 0,
                    "suspended_until": 0,
                    "banned_until": 0,
                    "delete_after": None,
                    "isDeleted": False
                },
                "last_login": None,
                "last_ip": None
            }
        )

        return True, FileWrite
    
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
        
        if not (type(username) == str):
            self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
            return False, False, None
        if not (self.files.does_item_exist("usersv0", str(username))):
            return False, True, None
        
        self.log("Reading account: {0}".format(username))
        FileRead, userdata = self.files.load_item("usersv0", str(username))
        
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
                "flags"
                "last_ip"
            ]:
                if sensitive in userdata:
                    del userdata[sensitive]
            FileCheck, FileRead, userdata["flags"] = self.get_flags(username, omitSensitive=True)
            if userdata["flags"]["deleted"]:
                return False, True, None
        elif isClient:
            for sensitive in [
                "pswd",
                "last_ip"
            ]:
                if sensitive in userdata:
                    del userdata[sensitive]

        return True, FileRead, userdata
    
    def get_flags(self, username, omitSensitive=False):
        """
        Returns 2 booleans, plus a payload.
        
        | FileCheck | FileRead | Definiton
        |---------|----------|-----------------
        |  True   |   True   | Account exists and read 
        |  True   |   False  | Account exists, read error
        |  False  |   True   | Account does not exist
        |  False  |   False  | Exception
        """
        
        if not (type(username) == str):
            self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
            return False, False, None
        if not self.files.does_item_exist("usersv0", str(username)):
            return False, True, None

        FileCheck, FileRead, userdata = self.get_account(username)
        if not (FileCheck and FileRead):
            return False, FileRead, {}
        else:
            userflags = userdata["flags"]

        if omitSensitive:
            payload = {
                "suspended": (userflags["suspended_until"] > int(time.time())),
                "banned": (userflags["banned_until"] > int(time.time())),
                "deleted": userflags["isDeleted"]
            }
        else:
            payload = {
                "locked": (userflags["locked_until"] > int(time.time())),
                "perm_locked": (userflags["locked_until"] == -1),
                "suspended": (userflags["suspended_until"] > int(time.time())),
                "banned": (userflags["banned_until"] > int(time.time())),
                "dormant": userflags["dormant"],
                "pending_deletion": (userflags["delete_after"] != None),
                "deleted": userflags["isDeleted"]
            }
        
        return True, FileRead, payload

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
        
        if not ((type(username) == str) and (type(password) == str)):
            self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
            return False, False, False
        if not self.files.does_item_exist("usersv0", str(username)):
            return False, True, False
        
        self.log("Authenticating account: {0}".format(username))
        FileRead, userdata = self.files.load_item("usersv0", str(username))
        if not FileRead:
            return True, False, False
        hashed_pw = userdata["pswd"]
        pswd_bytes = bytes(password, "utf-8")
        hashed_pw_bytes = bytes(hashed_pw, "utf-8")
        try:
            valid = bcrypt.checkpw(pswd_bytes, hashed_pw_bytes)
            self.log("Authenticating {0}: {1}".format(username, valid))
            return True, True, valid
        except:
            self.log("Error on authenticate: {0}".format(self.errorhandler()))
            return True, True, False
    
    def change_password(self, username, newpassword, strength=12):
        """
        Returns 3 booleans.
        
        | FileCheck | FileRead | FileWrite | Definiton
        |---------|----------|----------|-----------------
        |  True   |   True   |  True    | Account exists, read OK, password changed
        |  True   |   True   |  False   | Account exists, read OK, password not changed
        |  True   |   False  |  False   | Account exists, read error
        |  False  |   True   |  False   | Account does not exist
        |  False  |   False  |  False   | Exception
        """
        
        if not ((type(username) == str) and (type(newpassword) == str)):
            self.log("Error on get_account: Expected str for username and newpassword, got {0} for username, and {1} for newpassword".format(type(username), type(newpassword)))
            return False, False, False
        if not (self.files.does_item_exist("usersv0", str(username))):
            return False, True, False
        
        self.log("Changing {0} password".format(username))
        pswd_bytes = bytes(newpassword, "utf-8") # Convert password to bytes
        hashed_pw = bcrypt.hashpw(pswd_bytes, bcrypt.gensalt(strength)) # Hash and salt the password
        FileCheck, FileRead, FileWrite = self.update_setting(username, {"pswd": hashed_pw.decode()}, forceUpdate=True)
    
        return FileCheck, FileRead, FileWrite
    
    def update_setting(self, username, newdata, forceUpdate=False):
        """
        Returns 2 booleans.
        
        | FileCheck | FileWrite | Definiton
        |-----------|-----------|----------
        | True      | True      | Account exists, read OK, settings changed
        | True      | False     | Account exists, read OK, settings write error
        | False     | True      | Account does not exist
        | False     | False     | Exception
        """
        
        if not ((type(username) == str) and (type(newdata) == dict)):
            self.log("Error on update_setting: Expected str for username and dict for newdata, got {0} for username and {1} for newdata".format(type(username), type(newdata)))
            return False, False
        if not self.account_exists(username, False):
            return False, False

        self.log("Updating account settings: {0}".format(username))
        user_datatypes = {
            "theme": str,
            "mode": bool,
            "sfx": bool,
            "debug": bool,
            "bgm": bool,
            "bgm_song": int,
            "pfp_data": int,
            "quote": str
        }
        allowed_values = {
            "theme": ["orange", "blue"],
            "bgm_song": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "layout": ["new"],
            "pfp_data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
            "lvl": [1, 2, 3, 4]
        }
        new_userdata = {}

        for key, value in newdata.items():
            if (key in user_datatypes and type(value) == user_datatypes[key]) or forceUpdate:
                if (not key in allowed_values) or (value in allowed_values[key]):
                    if (key != "quote") or (len(value) <= 100):
                        new_userdata[key] = value
        FileWrite = self.files.update_item("usersv0", str(username), new_userdata)

        return True, FileWrite
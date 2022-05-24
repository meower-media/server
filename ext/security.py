import bcrypt
import secrets

"""
Meower Security Module
This module provides account management and authentication services.
"""

class Security:
    def __init__(self, meower):
        self.meower = meower
        self.err = meower.err
        self.log = meower.supporter.log
        self.errorhandler = meower.supporter.full_stack
        self.log("Security initialized!")

    def get_account(self, username: str):
        self.log("Getting account: {0}".format(username))
        userdata = self.meower.files.load_item("usersv0", username)
        
        client_userdata = userdata
        del client_userdata["pswd"]
        del client_userdata["last_ip"]

        current_time = self.meower.supporter.timestamp(7)
        flags = {
            "dormant": userdata["flags"]["dormant"],
            "temp_locked": (userdata["flags"]["locked_until"] > current_time),
            "perm_locked": (userdata["flags"]["locked_until"] == -1),
            "suspended": ((userdata["flags"]["suspended_until"] > current_time) or (userdata["flags"]["suspended_until"] == -1)),
            "banned": ((userdata["flags"]["banned_until"] > current_time) or (userdata["flags"]["banned_until"] == -1)),
            "pending_deletion": (userdata["flags"]["delete_after"] > current_time),
            "deleted": userdata["flags"]["isDeleted"]
        }

        profile = {
            "username": userdata["_id"],
            "lower_username": userdata["lower_username"],
            "pfp_data": userdata["pfp_data"],
            "quote": userdata["quote"],
            "lvl": userdata["lvl"],
            "flags": {
                "suspended": flags["suspended"],
                "banned": flags["banned"],
                "isDeleted": flags["deleted"]
            },
            "online": (userdata["_id"] in self.meower.cl.getUsernames())
        }

        return {
            "userdata": userdata,
            "client_userdata": client_userdata,
            "flags": flags,
            "profile": profile
        }

    def create_account(self, username: str, password: str):
        self.log("Creating account: {0}".format(username))
        pswd_bytes = bytes(password, "utf-8") # Convert password to bytes
        hashed_pw = bcrypt.hashpw(pswd_bytes, bcrypt.gensalt(12)) # Hash and salt the password
        self.meower.files.create_item("usersv0", username, { # Default account data
            "created": self.meower.supporter.timestamp(6),
            "lower_username": username.lower(),
            "theme": "orange",
            "mode": True,
            "sfx": True,
            "debug": False,
            "bgm": True,
            "bgm_song": 2,
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
        })
        token = self.create_token(username, expiry=2592000, type=1)
        return token

    def authenticate(self, username: str, password: str):
        userdata = self.get_account(username)
        flags = userdata["flags"]
        userdata = userdata["userdata"]
        if flags["dormant"]:
            raise self.err.AccDormant
        elif flags["temp_locked"]:
            raise self.err.AccTempLocked
        elif flags["perm_locked"]:
            raise self.err.AccPermLocked
        elif not bcrypt.checkpw(bytes(password, "utf-8"), bytes(userdata["pswd"], "utf-8")):
            raise self.err.InvalidPassword
        elif flags["banned"]:
            raise self.err.AccBanned
        elif flags["deleted"]:
            raise self.err.AccDeleted
        else:
            token = self.create_token(username, expiry=2592000, type=1)
            return token

    def update_config(self, username: str, newdata: dict, forceUpdate: bool):
        self.log("Updating account settings: {0}".format(username))

        user_datatypes = { # Valid datatypes for each key
            "theme": str,
            "mode": bool,
            "sfx": bool,
            "debug": bool,
            "bgm": bool,
            "bgm_song": int,
            "pfp_data": int,
            "quote": str
        }

        allowed_values = { # Allowed values for each key
            "theme": ["orange", "blue"],
            "bgm_song": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "layout": ["new"],
            "pfp_data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
            "lvl": [1, 2, 3, 4]
        }

        # Check if value is valid and store it
        new_userdata = {}
        for key, value in newdata.items():
            if (key in user_datatypes and type(value) == user_datatypes[key]) or forceUpdate:
                if (not key in allowed_values) or (value in allowed_values[key]):
                    if (key != "quote") or (len(value) <= 100):
                        new_userdata[key] = value
        
        # Write userdata to db
        self.meower.files.update_item("usersv0", username, new_userdata)

    def change_pswd(self, username: str, password: str):
        userdata = self.meower.files.load_item("usersv0", username)
        hashed_pswd = bcrypt.hashpw(bytes(password, "utf-8"), bcrypt.gensalt(12))
        self.update_config(username, {"pswd": hashed_pswd}, forceUpdate=True)
    
    def create_token(self, username: str, expiry: float=None, type: int=1):
        token = secrets.token_urlsafe(64)
        expires = self.meower.supporter.timestamp(7)+expiry
        self.meower.files.create_item("keys", self.meower.supporter.uuid(), {"token": token, "u": username, "created": self.meower.supporter.timestamp(6), "expires": expires, "renew_time": expiry, "type": type})
        return token
    
    def get_token(self, token: str):
        token_data = self.meower.files.load_item("keys", token)
        if ((token_data["created"] < self.meower.supporter.timestamp(6)+31536000) and (token_data["expires"] < self.meower.supporter.timestamp(7))) or (token_data["expires"] == -1):
            return token_data
        else:
            raise self.err.TokenExpired

    def renew_token(self, token: str):
        token_data = self.meower.files.load_item("keys", token)
        if (token_data["created"] < self.meower.supporter.timestamp(6)+31536000) and (token_data["renew_time"] != None):
            self.meower.files.update_item("keys", token, {"expires": self.meower.supporter.timestamp(7)+token_data["renew_time"]})
        else:
            raise self.err.TokenExpired
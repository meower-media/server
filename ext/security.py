import bcrypt
import secrets
from pytonik_ip_vpn_checker.ip import ip as ip_check

"""
Meower Security Module
This module provides account management and authentication services.
"""

class Security:
    def __init__(self, meower):
        self.meower = meower
        self.log = meower.supporter.log
        self.errorhandler = meower.supporter.full_stack
        self.log("Security initialized!")

    def get_account(self, username: str):
        self.log("Getting account: {0}".format(username))
        file_read, userdata = self.meower.files.load_item("usersv0", username)
        
        if not file_read:
            return False, None

        client_userdata = userdata.copy()
        del client_userdata["pswd"]
        del client_userdata["last_ip"]

        current_time = self.meower.supporter.timestamp(7)
        flags = {
            "dormant": userdata["flags"]["dormant"],
            "locked": ((userdata["flags"]["locked_until"] > current_time) or (userdata["flags"]["locked_until"] == -1)),
            "suspended": ((userdata["flags"]["suspended_until"] > current_time) or (userdata["flags"]["suspended_until"] == -1)),
            "banned": ((userdata["flags"]["banned_until"] > current_time) or (userdata["flags"]["banned_until"] == -1)),
            "pending_deletion": (userdata["flags"]["delete_after"] != None),
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

        return file_read, {
            "userdata": userdata,
            "client_userdata": client_userdata,
            "flags": flags,
            "profile": profile
        }

    def create_account(self, username: str, password: str):
        self.log("Creating account: {0}".format(username))
        pswd_bytes = bytes(password, "utf-8") # Convert password to bytes
        hashed_pw = bcrypt.hashpw(pswd_bytes, bcrypt.gensalt(12)) # Hash and salt the password
        file_write = self.meower.files.create_item("usersv0", username, { # Default account data
            "username": username,
            "lower_username": username.lower(),
            "created": self.meower.supporter.timestamp(6),
            "unread_inbox": False,
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
            "ratelimits": {
                "authentication": 0,
                "email_verification": 0,
                "reset_password": 0,
                "data_export": 0,
                "change_username": 0,
                "change_password": 0
            },
            "last_login": None,
            "last_ip": None
        })

        return file_write

    def check_password(self, username: str, password: str):
        file_read, userdata = self.get_account(username)
        if not file_read:
            return file_read, False
        password_bytes = bytes(password, "utf-8")
        stored_password_bytes = bytes(userdata["userdata"]["pswd"], "utf-8")
        valid = bcrypt.checkpw(password_bytes, stored_password_bytes)
        return file_read, valid

    def update_config(self, username: str, newdata: dict, forceUpdate: bool=False):
        self.log("Updating account settings: {0}".format(username))

        user_datatypes = { # Valid datatypes for each key
            "theme": str,
            "mode": bool,
            "sfx": bool,
            "debug": bool,
            "bgm": bool,
            "bgm_song": int,
            "pfp_data": int,
            "quote": str,
            "unread_inbox": bool
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
        return self.meower.files.update_item("usersv0", username, new_userdata)

    def change_pswd(self, username: str, password: str):
        userdata = self.meower.files.load_item("usersv0", username)
        hashed_pswd = bcrypt.hashpw(bytes(password, "utf-8"), bcrypt.gensalt(12))
        return self.update_config(username, {"pswd": hashed_pswd}, forceUpdate=True)
    
    def create_token(self, username: str, expiry: float=None, type: int=1):
        token = "Bearer {0}".format(secrets.token_urlsafe(64))
        expires = self.meower.supporter.timestamp(6)+expiry
        file_write = self.meower.files.create_item("keys", self.meower.supporter.uuid(), {"token": token, "u": username, "created": self.meower.supporter.timestamp(6), "expires": expires, "renew_time": expiry, "type": type})
        return file_write, token
    
    def get_token(self, token: str):
        session_id = self.meower.files.find_items("keys", {"token": token})
        if len(session_id) > 0:
            file_read, token_data = self.meower.files.load_item("keys", session_id[0])
            if file_read and (((token_data["created"] < self.meower.supporter.timestamp(6)+31536000) and (token_data["expires"] > self.meower.supporter.timestamp(6))) or (token_data["expires"] == -1)):
                return file_read, token_data
            else:
                return False, None
        else:
            return False, None

    def renew_token(self, token: str):
        file_read, token_data = self.meower.files.load_item("keys", token)
        if file_read and (token_data["created"] < self.meower.supporter.timestamp(6)+31536000) and (token_data["renew_time"] != None):
            return file_read, self.meower.files.update_item("keys", token, {"expires": self.meower.supporter.timestamp(6)+token_data["renew_time"]})
        else:
            return file_read, False
    
    def get_ip(self, ip: str):
        try:
            file_read, ip_data = self.meower.files.load_item("netlog", ip)
        except:
            ip_data = {
                "users": [],
                "last_user": None,
                "poisoned": False,
                "creation_blocked": False,
                "blocked": False
            }
            if ip_check.check(ip):
                ip_data["creation_blocked"] = True
            self.meower.files.create_item("netlog", ip, ip_data)
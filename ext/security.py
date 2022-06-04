import bcrypt
import secrets
import pyotp

"""
Meower Security Module
This module provides account management and authentication services.
"""

class Security:
    def __init__(self, meower):
        self.meower = meower
        self.log = meower.supporter.log
        self.errorhandler = meower.supporter.full_stack
        self.log("Security initialized!"))

    def get_account(self, user_id: str=None, username: str=None):
        if username is not None:
            index = self.meower.files.find_items("usersv0", {"lower_username": username.lower()})
            if len(index["index"]) != 0:
                user_id = index["index"][0]
        elif user_id is None:
            return False, None

        self.log("Getting account: {0}".format(user_id))
        file_read, userdata = self.meower.files.load_item("usersv0", user_id)
        if not file_read:
            return False, None

        client_userdata = userdata.copy()
        client_userdata["mfa"] = (client_userdata["mfa_secret"] != None)
        del client_userdata["mfa_secret"]
        del client_userdata["mfa_recovery"]
        del client_userdata["pswd"]
        del client_userdata["last_ip"]
        chats_index = self.meower.files.find_items("chats", {"members": {"$all": [user_id]}}, sort="nickname")
        client_userdata["chats_index"] = chats_index["index"]
        client_userdata["all_chats"] = chats_index["items"]

        current_time = self.meower.timestamp(7)
        flags = {
            "dormant": userdata["flags"]["dormant"],
            "locked": ((userdata["flags"]["locked_until"] > current_time) or (userdata["flags"]["locked_until"] == -1)),
            "suspended": ((userdata["flags"]["suspended_until"] > current_time) or (userdata["flags"]["suspended_until"] == -1)),
            "banned": ((userdata["flags"]["banned_until"] > current_time) or (userdata["flags"]["banned_until"] == -1)),
            "pending_deletion": (userdata["flags"]["delete_after"] != None),
            "deleted": userdata["flags"]["isDeleted"]
        }

        last_seen = self.meower.timestamp(6)-userdata["last_seen"]
        if last_seen == 0:
            last_seen = ""
        elif last_seen < 60:
            last_seen = "a moment ago"
        elif last_seen < 3600:
            last_seen = int(last_seen/60)
            if last_seen == 1:
                last_seen = "a minute ago"
            else:
                last_seen = "{0} minutes ago".format(last_seen)
        elif last_seen < 86400:
            last_seen = int(last_seen/3600)
            if last_seen == 1:
                last_seen = "an hour ago"
            else:
                last_seen = "{0} hours ago".format(last_seen)
        elif last_seen < 604800:
            last_seen = int(last_seen/86400)
            if last_seen == 1:
                last_seen = "yesterday"
            else:
                last_seen = "{0} days ago".format(last_seen)
        else:
            last_seen = int(last_seen/604800)
            if last_seen == 1:
                last_seen = "a week ago"
            else:
                last_seen = "{0} weeks ago".format(last_seen)

        status = {
            "status": "Banned" if flags["banned"] else userdata["user_status"] if (username in self.meower.ws.ulist) else "Offline",
            "last_seen": last_seen
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
            "status": status
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
            "created": self.meower.timestamp(6),
            "unread_inbox": False,
            "theme": "orange",
            "mode": True,
            "sfx": True,
            "debug": False,
            "bgm": True,
            "bgm_song": 2,
            "pfp_data": 1,
            "quote": "",
            "user_status": "Online",
            "last_seen": 0,
            "email": "",
            "pswd": hashed_pw.decode(),
            "mfa_secret": None,
            "mfa_recovery": None,
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

    def new_mfa_secret(self):
        return str(pyotp.random_base32())

    def check_mfa(self, username: str, code: str, custom_secret: str=None):
        if custom_secret != None:
            totp = pyotp.TOTP(custom_secret)
            return True, totp.verify(code)
        else:
            file_read, userdata = self.get_account(username)
            if not file_read:
                return file_read, False
            totp = pyotp.TOTP(userdata["userdata"]["mfa_secret"])
            
            return file_read, totp.verify(code)

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
            if ((key in user_datatypes) and (type(value) == user_datatypes[key])) or forceUpdate:
                if (not key in allowed_values) or (value in allowed_values[key]):
                    if (key != "quote") and (len(str(value)) <= 100):
                        new_userdata[key] = value
                    elif len(str(value)) < 6:
                        new_userdata[key] = value
            else:
                try:
                    new_userdata[key] = user_datatypes[key](value)
                    if (not key in allowed_values) or (value in allowed_values[key]):
                        if (key != "quote") and (len(str(value)) <= 100):
                            new_userdata[key] = value
                        elif len(str(value)) < 6:
                            new_userdata[key] = value
                except:
                    pass
        
        # Write userdata to db
        return self.meower.files.update_item("usersv0", username, new_userdata)

    def change_pswd(self, username: str, password: str):
        userdata = self.meower.files.load_item("usersv0", username)
        hashed_pswd = bcrypt.hashpw(bytes(password, "utf-8"), bcrypt.gensalt(12))
        return self.update_config(username, {"pswd": hashed_pswd}, forceUpdate=True)
    
    def create_token(self, username: str, expiry: float=None, type: int=1, device: str=None):
        token = str(secrets.token_urlsafe(64))
        if type == 1:
            token = "Bearer "+token
        elif type == 2:
            token = "MFA "+token
        expires = self.meower.timestamp(6)+expiry
        file_write = self.meower.files.create_item("keys", self.meower.supporter.uuid(), {"token": token, "u": username, "created": self.meower.timestamp(6), "expires": expires, "renew_time": expiry, "type": type, "device": device})
        return file_write, token
    
    def get_token(self, token: str):
        session_id = self.meower.files.find_items("keys", {"token": token})
        if len(session_id["index"]) == 0:
            return False, None
    
        token_data = session_id["items"][0]
        if not (((token_data["created"] < self.meower.timestamp(6)+31536000) and (token_data["expires"] > self.meower.timestamp(6))) or (token_data["expires"] == -1)):
            return False, None

        file_read, userdata = self.get_account(token_data["u"])
        if not file_read:
            return False, None

        if (userdata["userdata"]["flags"]["locked_until"] == -1) or userdata["flags"]["dormant"] or userdata["flags"]["deleted"] or userdata["flags"]["banned"] or userdata["flags"]["pending_deletion"] or userdata["flags"]["deleted"]:
            return False, None

        return file_read, token_data

    def renew_token(self, token: str, device: str="Unknown"):
        file_read, token_data = self.get_token(token)
        if file_read and (token_data["created"] < self.meower.timestamp(6)+31536000) and (token_data["renew_time"] != None):
            return file_read, self.meower.files.update_item("keys", token_data["_id"], {"expires": self.meower.timestamp(6)+token_data["renew_time"], "device": device})
        else:
            return file_read, False
    
    def delete_token(self, token: str):
        file_read, token_data = self.get_token(token)
        if file_read:
            return file_read, self.meower.files.delete_item("keys", token_data["_id"])
        return file_read, False

    def get_ip(self, ip: str):
        file_read, ip_data = self.meower.files.load_item("netlog", ip)
        if not file_read:
            file_read = True
            ip_data = {
                "users": [],
                "last_user": None,
                "poisoned": False,
                "creation_blocked": False,
                "blocked": False
            }
            self.meower.files.create_item("netlog", ip, ip_data)
        
        return file_read, ip_data
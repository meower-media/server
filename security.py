import bcrypt
import secrets
import time
import uuid
import json
import os
from datetime import datetime
import shutil
import threading

"""

Meower Security Module

This module provides account management and authentication services.

"""

class Security:
    def __init__(self, files, reemail, logger, errorhandler):
        self.bc = bcrypt
        self.files = files
        self.reemail = reemail
        
        self.log = logger
        self.errorhandler = errorhandler

        self.email_ratelimits = {
            "verifications": {},
            "password_resets": {},
            "account_deletions": {}
        }

        threading.Thread(target=self.scheduled_deletions).start()

        self.log("Security initialized!")
    
    def create_account(self, username, password, strength=12):
    
        """
        Returns 2 booleans.
        
        | FileCheck | FileWrite | Definiton
        |-----------|-----------|----------
        | True      | True      | Account created
        | True      | False     | Account creation error
        | False     | True      | Account already exists
        | False     | False     | Exception
        """
        
        if (type(password) == str) and (type(username) == str):
            if not self.account_exists(username, ignore_case=True):
                self.log("Creating account: {0}".format(username))
                pswd_bytes = bytes(password, "utf-8") # Convert password to bytes
                hashed_pswd = self.bc.hashpw(pswd_bytes, self.bc.gensalt(strength)) # Hash and salt the password
                result = self.files.create_item("usersv0", username, { # Default account data
                        "theme": "orange",
                        "mode": True,
                        "sfx": True,
                        "debug": False,
                        "bgm": True,
                        "bgm_song": 2,
                        "layout": "new",
                        "pfp_data": 1,
                        "quote": "",
                        "bots": [],
                        "lower_username": username.lower(),
                        "email": None,
                        "pswd": hashed_pswd.decode(),
                        "lvl": 0,
                        "created": int(time.time()),
                        "last_login": None,
                        "last_ip": None,
                        "locked_until": 0,
                        "compromised": False,
                        "delete_after": None,
                        "isDeleted": False
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
        |-----------|----------|----------
        | True      | True     | Account exists and read 
        | True      | False    | Account exists, read error
        | False     | True     | Account does not exist
        | False     | False    | Exception
        """
        
        if type(username) == str:
            if self.account_exists(username, False):
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
                        "last_ip",
                        "delete_after"
                    ]:
                        del accountData[sensitive]
                
                if isClient:
                    if "email" in accountData:
                        del accountData["email"]
                    if "pswd" in accountData:
                        del accountData["pswd"]
                    if "last_ip" in accountData:
                        del accountData["last_ip"]
                    if "delete_after" in accountData:
                        del accountData["delete_after"]
                
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
        |-----------|----------|-----------|----------
        | True      | True     | True      | Account exists, read OK, authentication valid
        | True      | True     | False     | Account exists, read OK, authentication invalid
        | True      | False    | False     | Account exists, read error
        | False     | True     | False     | Account does not exist
        | False     | False    | False     | Exception
        """
        
        if type(username) == str:
            if self.account_exists(username, False):
                self.log("Authenticating account: {0}".format(username))
                FileCheck, FileRead, userdata = self.get_account(username, False, False)
                if FileCheck and FileRead:
                    FileCheck, FileRead, isBot, Verified = self.is_account_bot(username)
                    if FileCheck and FileRead:
                        if not isBot:
                            hashed_pw = userdata["pswd"]
                            pswd_bytes = bytes(password, "utf-8")
                            hashed_pw_bytes = bytes(hashed_pw, "utf-8")
                            result = self.bc.checkpw(pswd_bytes, hashed_pw_bytes)
                            self.log("Authenticating {0}: {1}".format(username, result))
                            return FileCheck, FileRead, result
                        else:
                            return FileCheck, FileRead, False
                    else:
                        return FileCheck, FileRead, False
                else:
                    return FileCheck, FileRead, False
            else:
                return False, True, False
        else:
            self.log("Error on authenticate: Expected str for username, got {0}".format(type(username)))
            return False, False, False
    
    def change_email(self, username, email, strength=12):
        if (type(username) == str) and (type(email) == str):
            if self.account_exists(username, False):
                # Ratelimits
                if username in self.email_ratelimits["verifications"]:
                    if self.email_ratelimits["verifications"][username] > int(time.time()):
                        return False, True
                self.email_ratelimits["verifications"][username] = int(time.time())+300

                # Hash email
                email_bytes = bytes(email, "utf-8") # Convert email to bytes
                hashed_email = self.bc.hashpw(email_bytes, self.bc.gensalt(strength))

                # Create token
                result, token = self.create_token(4, username, hashed_email.decode())
                if result:
                    # Send verification email
                    self.reemail.send_verification([email], username, token)
                    return True, False
                else:
                    return False, False
            else:
                return False, False
        else:
            return False, False

    def reset_pswd(self, username, email):
        if (type(username) == str) and (type(email) == str):
            if self.files.does_item_exist("usersv0", str(username)):
                # Ratelimits
                if username in self.email_ratelimits["password_resets"]:
                    if self.email_ratelimits["password_resets"][username] > int(time.time()):
                        return False, True
                self.email_ratelimits["password_resets"][username] = int(time.time())+300

                # Create token
                result, token = self.create_token(5, username, None)
                if result:
                    # Send password reset email
                    self.reemail.send_password_reset([email], username, token)
                    return True, False
                else:
                    return False, False
            else:
                return False, False
        else:
            return False, False

    def change_password(self, username, newpassword, strength=12):

        """
        Returns 3 booleans.
        
        | FileCheck | FileRead | FileWrite | Definiton
        |-----------|----------|-----------|----------
        | True      | True     | True      | Account exists, read OK, password changed
        | True      | True     | False     | Account exists, read OK, password not changed
        | True      | False    | False     | Account exists, read error
        | False     | True     | False     | Account does not exist
        | False     | False    | False     | Exception
        """
        
        if (type(username) == str) and (type(newpassword) == str):
            if self.files.does_item_exist("usersv0", str(username)):
                self.log("Changing {0} password".format(username))
                result, accountData = self.files.load_item("usersv0", str(username))
                if result:
                    try:
                        pswd_bytes = bytes(newpassword, "utf-8") # Convert password to bytes
                        hashed_pswd = self.bc.hashpw(pswd_bytes, self.bc.gensalt(strength)) # Hash and salt the password
                        
                        accountData["pswd"] = hashed_pswd.decode()
                        
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
            self.log("Error on change_password: Expected str for username and newpassword, got {0} for username, and {1} for newpassword".format(type(username), type(newpassword)))
            return False, False, False
    
    def account_exists(self, username, ignore_case=False):
        if type(username) == str:
            if ignore_case:
                payload = self.files.find_all("usersv0", {"lower_username": username.lower()})
                if len(payload) == 0:
                    return False
                else:
                    return True
            else:
                return self.files.does_item_exist("usersv0", username)
        else:
            self.log("Error on account_exists: Expected str for username, got {0}".format(type(username)))
            return False

    def get_infractions(self, username):
        if type(username) == str:
            if self.account_exists(username):
                active_infractions = []
                infractions_index = self.files.find_all("jail", {"u": username, "isDeleted": False})
                for item in infractions_index:
                    result, payload = self.files.load_item("jail", item)
                    if result:
                        if payload["expires"] == None or payload["expires"] > int(time.time()):
                            if payload["type"] == 1:
                                active_infractions.append("suspended")
                            elif payload["type"] == 2:
                                active_infractions.append("banned")
                            elif payload["type"] == 3:
                                active_infractions.append("terminated")
                return True, True, active_infractions
            else:
                return False, True, []
        else:
            return False, False, []

    def account_status(self, username):

        """
        Returns 9 booleans.
        
        | FileCheck | FileRead | Email Verified | Locked | Compromised | Banned | Terminated | Deleted | Pending Deletion | Definiton
        |-----------|----------|----------------|--------|-------------|--------|------------|---------|------------------|----------
        | False     | True     | False          | False  | False       | False  | False      | False   | False            | Account doesn't exist, read OK
        | True      | True     | False          | False  | False       | False  | False      | False   | False            | Account exists, read OK, email not verified
        | True      | True     | True           | False  | False       | False  | False      | False   | False            | Account exists, read OK, account OK
        | True      | True     | True           | True   | False       | False  | False      | False   | False            | Account exists, read OK, account locked
        | True      | True     | True           | False  | True        | False  | False      | False   | False            | Account exists, read OK, account compromised
        | True      | True     | True           | False  | False       | True   | False      | False   | False            | Account exists, read OK, account banned
        | True      | True     | True           | False  | False       | False  | True       | False   | False            | Account exists, read OK, account terminated
        | True      | True     | True           | False  | False       | False  | False      | True    | False            | Account exists, read OK, account deleted
        | True      | True     | True           | False  | False       | False  | False      | False   | True             | Account exists, read OK, account pending deleted
        | False     | False    | True           | False  | False       | False  | False      | False   | Exception        | Exception
        """

        if type(username) == str:
            if self.account_exists(username, False):
                FileCheck, FileRead, userdata = self.get_account(username, False, False)
                if FileCheck and FileRead:
                    FileCheck, FileRead, active_infractions = self.get_infractions(username)
                    if FileCheck and FileRead:
                        return FileCheck, FileRead, (userdata["email"] != None), (userdata["locked_until"] > int(time.time())), userdata["compromised"], ("banned" in active_infractions), ("terminated" in active_infractions), userdata["isDeleted"], (userdata["delete_after"] != None)
                    else:
                        return FileCheck, FileRead, False, False, False, False, False, False, False
            else:
                return False, True, False, False, False, False, False, False, False
        else:
            return False, False, False, False, False, False, False, False, False

    def is_account_bot(self, username):

        """
        Returns 4 booleans.
        
        | FileCheck | FileRead | Is Bot | Verified | Definiton
        |-----------|----------|--------|----------|----------
        | True      | True     | True   | False    | Account exists and read, account is bot, not verified
        | True      | True     | True   | True     | Account exists and read, account is bot, verified
        | True      | True     | False  | False    | Account exists and read, account is NOT bot
        | True      | False    | False  | False    | Account exists, read error
        | False     | True     | False  | False    | Account does not exist
        | False     | False    | False  | False    | Exception
        """
        
        if type(username) == str:
            if self.account_exists(username, False):
                self.log("Reading account: {0}".format(username))
                FileCheck, FileRead, userdata = self.get_account(username, True, False)
                if FileCheck and FileRead:
                    if userdata["lvl"] == -1:
                        return FileCheck, FileRead, True, False
                    elif userdata["lvl"] == -2:
                        return FileCheck, FileRead, True, True
                    else:
                        return FileCheck, FileRead, False, False
                else:
                    return FileCheck, FileRead, False, False
            else:
                return False, True, False, False
        else:
            self.log("Error on is_account_bot: Expected str for username, got {0}".format(type(username)))
            return False, False, False, False

    def is_email_verified(self, username):

        """
        Returns 3 booleans.
        
        | FileCheck | FileRead | Verified | Definiton
        |-----------|----------|----------|----------
        | True      | True     | True     | Account exists and read, account is bot, not verified
        | True      | True     | True     | Account exists and read, account is bot, verified
        | True      | True     | False    | Account exists and read, account is NOT bot
        | True      | False    | False    | Account exists, read error
        | False     | True     | False    | Account does not exist
        | False     | False    | False    | Exception
        """
        
        if type(username) == str:
            if self.account_exists(username, False):
                self.log("Reading account: {0}".format(username))
                FileCheck, FileRead, userdata = self.get_account(username, False, False)
                if FileCheck and FileRead:
                    if userdata["email"] != None:
                        return FileCheck, FileRead, True
                    else:
                        return FileCheck, FileRead, False
                else:
                    return FileCheck, FileRead, False
            else:
                return False, True, False
        else:
            self.log("Error on is_email_verified: Expected str for username, got {0}".format(type(username)))
            return False, False, False

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
        
        if (type(username) == str) and (type(newdata) == dict):
            if self.account_exists(username, False):
                self.log("Updating account settings: {0}".format(username))
                datatypes = {
                    "theme": str,
                    "mode": bool,
                    "sfx": bool,
                    "debug": bool,
                    "bgm": bool,
                    "bgm_song": int,
                    "layout": str,
                    "pfp_data": int,
                    "quote": str,
                }
                secure_datatypes = {
                    "email": str,
                    "pswd": str,
                    "lvl": int,
                    "last_ip": str,
                    "last_login": int,
                    "bots": list,
                    "locked_until": str,
                    "compromised": bool,
                    "delete_after": int,
                    "isDeleted": bool
                }
                allowed_values = {
                    "theme": ["orange", "blue"],
                    "bgm_song": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                    "layout": ["old", "new"],
                    "pfp_data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
                    "lvl": [1, 2, 3, 4]
                }
                new_userdata = {}

                for key, value in newdata.items():
                    if (key in datatypes and type(value) == datatypes[key]) or (forceUpdate and key in secure_datatypes and type(value) == secure_datatypes[key]):
                        if (not key in allowed_values) or (value in allowed_values[key]):
                            if (key != "quote") or (len(value) <= 100):
                                new_userdata[key] = value
                result = self.files.update_item("usersv0", str(username), new_userdata)
                self.log("Updating {0} account settings: {1}".format(username, result))
                return True, result
            else:
                return False, False
        else:
            self.log("Error on update_setting: Expected str for username and dict for newdata, got {0} for username and {1} for newdata".format(type(username), type(newdata)))
            return False, False
        
    def scheduled_deletions(self):
        while True:
            time.sleep(5) # Checks for pending deletions every minute
            users_pending_deletions = self.files.find_all("usersv0", {"delete_after": {"$lte": int(time.time())}})
            for username in users_pending_deletions:
                FileCheck, FileRead, userdata = self.get_account(username, False, False)
                if FileCheck and FileRead:
                    if userdata["delete_after"] != None:
                        self.log("Starting deletion process for {0}".format(username))
                        if userdata["isDeleted"]: # Purge account
                            FileWrite = self.files.delete_item("usersv0", username) # Delete userdata file
                            if FileWrite:
                                self.log("{0} has been purged".format(username))
                                threading.Thread(target=self.purge_data, args=(username,)).start() # Purge all data
                                self.log("Starting full data purge for {0}".format(username))
                            else:
                                self.log("Failed to purge {0}".format(username))
                        else: # "Soft" delete account
                            FileCheck, FileWrite = self.update_setting(username, {"delete_after": int(time.time())+1209600, "isDeleted": True}, forceUpdate=True)
                            if FileCheck and FileWrite:
                                self.log("{0} has been deleted and will be fully purged in 14 days".format(username))
                            else:
                                self.log("Failed to delete {0}".format(username))
                    else:
                        self.log("Failed to start deletion process for {0}: Account not scheduled for deletion".format(username))
                else:
                    if ((not FileCheck) and FileRead):
                        # Account doesn't exist
                        self.log("Failed to start deletion process for {0}: Account not found".format(username))
                    else:
                        # Some other error
                        self.log("Failed to stat deletion process for {0}: Failed to read userdata".format(username))

    def purge_data(self, username):
        FileCheck, FileRead, userdata = self.get_account(username, False, False)
        if FileCheck and FileRead:
            FileCheck, FileRead, isBot, isVerified = self.is_account_bot(username)
            if isBot:
                self.files.update_all("posts", {"u": username, "type": 1}, {"u": "Deleted"}) # Set author of posts to 'Deleted'
            else:
                self.files.delete_all("posts", {"u": username, "type": 1}) # Purge all posts
            self.files.delete_all("posts", {"u": username, "type": 3}) # Purge all inbox messages
            self.files.update_all("posts", {"u": username, "type": 2}, {"u": "Deleted"}) # Set author of announcements to 'Deleted'

            # Remove user from chats (delete chats if they're the owner)
            all_chats = self.files.find_all("chats", {"members": {"$all": [username]}})
            for chatid in all_chats:
                FileRead, chatdata = self.files.load_item("chats", chatid)
                if FileRead:
                    if chatdata["owner"] == username:
                        self.files.delete_item("chats", chatid)
                    else:
                        chatdata["members"].remove(username)
                        self.files.update_item("chats", chatid, {"members": chatdata["members"]})

            # Delete all moderation stuff
            self.files.delete_all("jail", {"u": username}) # Delete all infractions
            self.files.update_all("jail", {"moderator": username}, {"moderator": "Deleted"}) # Set moderator of infractions given to 'Deleted'
            self.files.update_all("reports", {"reviewer": username}, {"reviewer": "Deleted"}) # Set reviewer of reports reviewed to 'Deleted'
            all_ips = self.files.find_all("netlog", {"users": {"$all": [username]}})
            for ip in all_ips:
                FileRead, netdata = self.files.load_item("netlog", ip)
                if FileRead:
                    netdata["users"].remove(username)
                    self.files.update_item("netlog", ip, {"users": netdata["users"]})
            FileRead, ipbanlist = self.files.load_item("config", "IPBanlist")
            if FileRead:
                if username in ipbanlist["users"]:
                    ipbanlist["users"].remove(username)

            return True
        else:
            return False

    def create_token(self, tokentype, username, email=None):
        if (type(tokentype) == int) and (type(username) == str) and (type(email) == None or type(email) == str):
            if tokentype == 1:
                expires = int(time.time())+259200
                token = "{0}.{1}".format(secrets.token_urlsafe(64), time.time())
            elif tokentype == 2:
                expires = None
                token = "{0}.{1}".format(secrets.token_urlsafe(64), time.time())
            elif tokentype == 3:
                expires = int(time.time())+3600
                token = "{0}.{1}".format(secrets.token_urlsafe(64), time.time())
            elif tokentype == 4:
                expires = int(time.time())+86400
                token = str(secrets.token_urlsafe(128))
            elif tokentype == 5:
                expires = int(time.time())+600
                token = str(secrets.token_urlsafe(128))
            result = self.files.create_item("keys", token, {"type": tokentype, "u": username, "email": email, "expires": expires})
            return result, token
        else:
            self.log("Error on create_token: Expected int for tokentype and str for username and str for email, got {0} for tokentype and {1} for username and {2} for email".format(type(tokentype), type(username), type(email)))
            return False, None

    def get_token(self, token):
        if type(token) == str:
            result, tokendata = self.files.load_item("keys", str(token))
            if result and (tokendata["expires"] == None or tokendata["expires"] > int(time.time())):
                username = tokendata["u"]
                FileCheck, FileRead, email_verified, locked, compromised, banned, terminated, deleted, pending_deletion = self.account_status(username)
                if FileCheck and FileRead:
                    if ((email_verified or tokendata["type"] >= 4 or tokendata["type"] <= 7) and (not compromised) and (not banned) and (not terminated) and (not deleted) and (not pending_deletion)):
                        return True, tokendata
                    else:
                        return False, None
                else:
                    return False, None
            else:
                if result:
                    self.files.delete_item("keys", str(token))
                return False, None
    
    def renew_token(self, token):
        result, payload = self.files.load_item("keys", str(token))
        if result:
            if payload["type"] == 1 or payload["type"] == 3:
                if payload["type"] == 1:
                    expires = int(time.time())+259200
                elif payload["type"] == 3:
                    expires = int(time.time())+3600
                return self.files.update_item("keys", str(token), {"expires": expires})
            else:
                return True
        else:
            return False

    def export_data(self, username, email):
        export_id = str(uuid.uuid4())
        posts_index = {}

        # Create export file structure
        os.mkdir("api/exports/{0}".format(export_id))
        os.mkdir("api/exports/{0}/posts".format(export_id))
        os.mkdir("api/exports/{0}/chats".format(export_id))
        os.mkdir("api/exports/{0}/bots".format(export_id))
        os.mkdir("api/exports/{0}/infractions".format(export_id))
        os.mkdir("api/exports/{0}/logs".format(export_id))

        # Export userdata
        FileCheck, FileRead, userdata = self.get_account(username, False, False)
        if FileCheck and FileRead:
            FileCheck, FileRead, EmailVerified, Locked, Compromised, Banned, Terminated, Deleted, PendingDeletion = self.account_status(username)
            FileCheck, FileRead, isBot, isVerified = self.is_account_bot(username)
            FileRead, active_infractions = self.get_infractions(username)
            userdata_export = {}
            userdata_export["username"] = userdata["_id"]
            userdata_export["profile_quote"] = userdata["quote"]
            userdata_export["profile_picture"] = userdata["pfp_data"]
            userdata_export["account_level"] = userdata["lvl"]
            userdata_export["config"] = {"theme": userdata["theme"], "mode": userdata["mode"], "sfx": userdata["sfx"], "debug": userdata["debug"], "bgm": userdata["bgm"], "bgm_song": userdata["bgm_song"], "layout": userdata["layout"]}
            userdata_export["flags"] = {"email_verified": EmailVerified, "isBot": isBot, "verified_bot": isVerified, "locked": Locked, "compromised": Compromised, "banned": Banned, "terminated": Terminated, "deleted": Deleted, "pending_deletion": PendingDeletion, "active_infractions": active_infractions}
            userdata_export["created"] = datetime.fromtimestamp(userdata["created"]).strftime("%d/%m/%Y %H:%M:%S %Z")
            userdata_export["last_login"] = datetime.fromtimestamp(userdata["last_login"]).strftime("%d/%m/%Y %H:%M:%S %Z")
            userdata_export["reported_posts"] = self.files.find_all("reports", {"type": 1, "reported": {"users": {"$all": [username]}}})
            userdata_export["reported_profiles"] = self.files.find_all("reports", {"type": 2, "reported": {"users": {"$all": [username]}}})
            userdata_export["last_ip"] = userdata["last_ip"]
            userdata_export["all_ips"] = self.files.find_all("netlog", {"users": {"$all": [username]}})
            userdata_export["isDeleted"] = Deleted
            with open("admin/exports/{0}/user.json".format(export_id), 'w') as f:
                json.dump(userdata_export, f, indent=4)
        else:
            with open("admin/exports/{0}/user.json".format(export_id), 'w') as f:
                json.dump({"username": username, "isDeleted": True}, f, indent=4)

        # Export posts
        for post_id in self.files.find_all("posts", {"u": username}):
            result, postdata = self.files.load_item("posts", post_id)
            if result:
                try:
                    del postdata["_id"]
                    if postdata["post_origin"] in posts_index:
                        posts_index[postdata["post_origin"]].append(post_id)
                    else:
                        posts_index[postdata["post_origin"]] = [post_id]
                    if not postdata["post_origin"] in os.listdir("admin/exports/{0}/posts".format(export_id)):
                        os.mkdir("admin/exports/{0}/posts/{1}".format(export_id, postdata["post_origin"]))
                    with open("admin/exports/{0}/posts/{1}/{2}.json".format(export_id, postdata["post_origin"], post_id), 'w') as f:
                        json.dump(postdata, f, indent=4)
                except Exception as e:
                    self.log("Failed exporting post data on export: {0}".format(e))
        with open("admin/exports/{0}/posts/index.json".format(export_id), 'w') as f:
            json.dump(posts_index, f, indent=4)

        # Export group chats
        for chat_id in self.files.find_all("chats", {"members": {"$all": [username]}}):
            result, chatdata = self.files.load_item("chats", chat_id)
            if result:
                try:
                    del chatdata["_id"]
                    chatdata["chatid"] = chat_id
                    with open("admin/exports/{0}/chats/{1}.json".format(export_id, chat_id), 'w') as f:
                        json.dump(chatdata, f, indent=4)
                except Exception as e:
                    self.log("Failed exporting chat data on export: {0}".format(e))

        # Export infractions
        for infraction_id in self.files.find_all("jail", {"u": username}):
            result, infractiondata = self.files.load_item("jail", infraction_id)
            if result:
                try:
                    del infractiondata["_id"]
                    del infractiondata["moderator"]
                    infractiondata["chatid"] = infraction_id
                    with open("admin/exports/{0}/infractions/{1}.json".format(export_id, infraction_id), 'w') as f:
                        json.dump(infractiondata, f, indent=4)
                except Exception as e:
                    self.log("Failed exporting chat data on export: {0}".format(e))

        # Create README file
        with open("admin/exports/{0}/README.txt".format(export_id), 'w') as f:
            f.write("This is a test data export!\n\nExported Account: {0}\n\nExport ID: {1}\n\nExport Time (epoch): {2}".format(username, export_id, datetime.now().strftime("%d/%m/%Y %H:%M:%S %Z")))

        # Create downloadable archive
        shutil.make_archive("admin/exports/{0}".format(export_id), "zip", "admin/exports/{0}".format(export_id))

        # Cleanup exported files
        shutil.rmtree("admin/exports/{0}".format(export_id))
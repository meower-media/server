from hashlib import sha256
import time
import requests
import os
import uuid

"""
Meower Security Module
This module provides account management and authentication services.
"""

SENSITIVE_ACCOUNT_FIELDS = {
    "pswd",
    "tokens",
    "delete_after"
}

SENSITIVE_ACCOUNT_FIELDS_DB_PROJECTION = {}
for key in SENSITIVE_ACCOUNT_FIELDS:
    SENSITIVE_ACCOUNT_FIELDS_DB_PROJECTION[key] = 0

DEFAULT_USER_SETTINGS = {
    "unread_inbox": True,
    "theme": "orange",
    "mode": True,
    "layout": "new",
    "sfx": True,
    "bgm": False,
    "bgm_song": 2,
    "debug": False,
    "hide_blocked_users": False,
    "active_dms": [],
    "favorited_chats": []
}

AUDIT_LOG_TYPES = {
    "got_notes",
    "updated_notes",

    "got_user",
    "got_inbox",

    "cleared_posts",
    "alerted",
    "kicked",
    "force_kicked",
    "banned",

    "sent_announcement",

    "kicked_all"
}


class UserFlags:
    SYSTEM = 1
    DELETED = 2


class Permissions:
    SYSADMIN = 1

    VIEW_REPORTS = 2
    EDIT_REPORTS = 4

    VIEW_NOTES = 8
    EDIT_NOTES = 16

    VIEW_POSTS = 32
    DELETE_POSTS = 64

    VIEW_ALTS = 128
    SEND_ALERTS = 256
    KICK_USERS = 512
    CLEAR_USER_QUOTES = 1024
    VIEW_BAN_STATES = 2048
    EDIT_BAN_STATES = 4096
    DELETE_USERS = 8192

    VIEW_IPS = 16384
    BLOCK_IPS = 32768

    VIEW_CHATS = 65536
    EDIT_CHATS = 131072

    SEND_ANNOUNCEMENTS = 262144

class Security:
    def __init__(self, files, supporter, logger, errorhandler):
        self.supporter = supporter
        self.files = files
        self.log = logger
        self.errorhandler = errorhandler
        self.log("Security initialized!")

    def account_exists(self, username, ignore_case=False):
        if not isinstance(username, str):
            self.log("Error on account_exists: Expected str for username, got {0}".format(type(username)))
            return False

        return (self.files.db.usersv0.count_documents({"lower_username": username.lower()} if ignore_case else {"_id": username}, limit=1) > 0)
    
    def get_account(self, username, include_config=False):
        # Check datatype
        if not isinstance(username, str):
            self.log("Error on get_account: Expected str for username, got {0}".format(type(username)))
            return None

        # Get account
        account = self.files.db.usersv0.find_one({"lower_username": username.lower()}, projection=SENSITIVE_ACCOUNT_FIELDS_DB_PROJECTION)
        if not account:
            return None

        # Make sure there's nothing sensitive on the account obj
        for key in SENSITIVE_ACCOUNT_FIELDS:
            if key in account:
                del account[key]

        # Add lvl and banned
        account["lvl"] = 0
        if account["ban"]:
            if account["ban"]["state"] == "PermBan":
                account["banned"] = True
            elif (account["ban"]["state"] == "TempBan") and (account["ban"]["expires"] > time.time()):
                account["banned"] = True
            else:
                account["banned"] = False
        else:
            account["banned"] = False

        # Include config
        if include_config:
            account.update(DEFAULT_USER_SETTINGS)
            user_settings = self.files.db.user_settings.find_one({"_id": account["_id"]})
            if user_settings:
                del user_settings["_id"]
                account.update(user_settings)
        else:
            # Remove ban if not including config
            del account["ban"]

        return account

    def update_settings(self, username, newdata):
        # Check datatype
        if not isinstance(username, str):
            self.log("Error on update_settings: Expected str for username, got {0}".format(type(username)))
            return False
        elif not isinstance(newdata, dict):
            self.log("Error on update_settings: Expected str for newdata, got {0}".format(type(newdata)))
            return False
        
        # Get user UUID
        account = self.files.db.usersv0.find_one({"lower_username": username.lower()}, projection={"_id": 1, "uuid": 1})
        if not account:
            return False
        
        # Init vars
        updated_user_vals = {}
        updated_user_settings_vals = {}

        # Update pfp
        if "pfp_data" in newdata:
            if isinstance(newdata["pfp_data"], int):
                updated_user_vals["pfp_data"] = newdata["pfp_data"]
        
        # Update quote
        if "quote" in newdata:
            if isinstance(newdata["quote"], str) and len(newdata["quote"]) <= 360:
                updated_user_vals["quote"] = newdata["quote"]

        # Update settings
        for key, default_val in DEFAULT_USER_SETTINGS.items():
            if key in newdata:
                if isinstance(newdata[key], type(default_val)):
                    if key == "favorited_chats" and len(newdata[key]) > 50:
                        newdata[key] = newdata[key][:50]
                    
                    updated_user_settings_vals[key] = newdata[key]

        # Update database items
        if len(updated_user_vals) > 0:
            self.files.db.usersv0.update_one({"_id": account["_id"]}, {"$set": updated_user_vals})
        if len(updated_user_settings_vals) > 0:
            self.files.db.user_settings.update_one({"_id": account["_id"]}, {"$set": updated_user_settings_vals}, upsert=True)

        return True

    def get_ban_state(self, username):
        if not isinstance(username, str):
            self.log("Error on get_ban_state: Expected str for username, got {0}".format(type(username)))
            return "None"

        account = self.files.db.usersv0.find_one({"lower_username": username.lower()}, projection={"ban": 1})
        if not account:
            return "None"
        elif (account["ban"]["state"] in {"TempRestriction", "TempSuspension", "TempBan"}) and (account["ban"]["expires"] < time.time()):
            return "None"
        else:
            return account["ban"]["state"]

    def get_permissions(self, username):
        if not isinstance(username, str):
            self.log("Error on get_permissions: Expected str for username, got {0}".format(type(username)))
            return 0

        account = self.files.db.usersv0.find_one({"lower_username": username.lower()}, projection={"permissions": 1})
        if account:
            return account["permissions"]
        else:
            return 0

    def has_permission(self, user_permissions, permission):
        if ((user_permissions & Permissions.SYSADMIN) == Permissions.SYSADMIN):
            return True
        else:
            return ((user_permissions & permission) == permission)

    def delete_account(self, username, purge=False):
        # Get account
        account = self.files.db.usersv0.find_one({"_id": username}, projection={"uuid": 1, "flags": 1})
        if not account:
            return

        # Add deleted flag
        account["flags"] |= UserFlags.DELETED

        # Update account
        self.files.db.usersv0.update_one({"_id": username}, {"$set": {
            "pfp_data": None,
            "quote": None,
            "pswd": None,
            "tokens": None,
            "flags": account["flags"],
            "permissions": None,
            "ban": None,
            "last_seen": None,
            "delete_after": None
        }})

        # Kick user
        self.supporter.kickUser(username, status="LoggedOut")

        # Delete user settings
        self.files.db.user_settings.delete_one({"_id": username})

        # Delete netlogs
        self.files.db.netlog.delete_many({"_id.user": username})

        # Remove from reports
        self.files.db.reports.update_many({"reports.user": username}, {"$pull": {
            "reports": {"user": username}
        }})

        # Delete relationships
        self.files.db.relationships.delete_many({"$or": [
            {"_id.from": username},
            {"_id.to": username}
        ]})

        # Update or delete chats
        for chat in self.files.db.chats.find({
            "$or": [
                {"deleted": False},
                {"deleted": True}
            ],
            "members": username
        }, projection={"type": 1, "owner": 1, "members": 1}):
            if chat["type"] == 1 or len(chat["members"]) == 1:
                self.files.db.posts.delete_many({"post_origin": chat["_id"], "isDeleted": False})
                self.files.db.chats.delete_one({"_id": chat["_id"]})
            else:
                if chat["owner"] == username:
                    chat["owner"] = "Deleted"
                chat["members"].remove(username)
                self.files.db.chats.update_one({"_id": chat["_id"]}, {"$set": {
                    "owner": chat["owner"],
                    "members": chat["members"]
                }})

        # Delete posts
        self.files.db.posts.delete_many({"u": username})

        # Purge user
        if purge:
            self.files.db.reports.delete_many({"content_id": username, "type": "user"})
            self.files.db.admin_notes.delete_one({"_id": account["uuid"]})
            self.files.db.usersv0.delete_one({"_id": username})

    def get_netinfo(self, ip_address):
        """
        Get IP info from IPHub.

        Returns:
        ```json
        {
            "_id": str,
            "ip": str,
            "country_code": str,
            "country_name": str,
            "asn": int,
            "isp": str,
            "vpn": bool
        }
        ```
        """

        # Get IP hash
        ip_hash = sha256(ip_address.encode()).hexdigest()

        # Get from database or IPHub if not cached
        netinfo = self.files.db.netinfo.find_one({"_id": ip_hash})
        if not netinfo:
            iphub_key = os.getenv("IPHUB_KEY")
            if iphub_key:
                iphub_info = requests.get(f"http://v2.api.iphub.info/ip/{ip_address}", headers={
                    "X-Key": iphub_key
                }).json()
                netinfo = {
                    "_id": ip_hash,
                    "ip": iphub_info["ip"],
                    "country_code": iphub_info["countryCode"],
                    "country_name": iphub_info["countryName"],
                    "asn": iphub_info["asn"],
                    "isp": iphub_info["isp"],
                    "vpn": (iphub_info["block"] == 1),
                    "last_refreshed": int(time.time())
                }
                self.files.db.netinfo.update_one({"_id": ip_hash}, {"$set": netinfo}, upsert=True)
            else:
                netinfo = {
                    "_id": ip_hash,
                    "ip": ip_address,
                    "country_code": "Unknown",
                    "country_name": "Unknown",
                    "asn": "Unknown",
                    "isp": "Unknown",
                    "vpn": False,
                    "last_refreshed": int(time.time())
                }

        return netinfo
    
    def add_audit_log(self, action_type, mod_username, mod_ip, data):
        self.files.db.audit_log.insert_one({
            "_id": str(uuid.uuid4()),
            "type": action_type,
            "mod_username": mod_username,
            "mod_ip": mod_ip,
            "time": int(time.time()),
            "data": data
        })

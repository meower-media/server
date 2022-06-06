import bcrypt
import secrets
import pyotp
from uuid import uuid4
import time

"""
Meower Accounts Module
This module provides account management and authentication services.
"""

class Accounts:
    def __init__(self, meower):
        self.meower = meower
        self.log = meower.supporter.log
        self.errorhandler = meower.supporter.full_stack
        self.log("Accounts initialized!")

    def create_account(self, username, password=None, uid=None):
        if uid is None:
            uid = str(uuid4())
        if password is not None:
            hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12))
        self.meower.db["usersv0"].insert_one({
            "_id": uid,
            "username": username,
            "lower_username": username.lower(),
            "created": int(time.time()),
            "config": {
                "unread_inbox": False,
                "theme": "orange",
                "mode": True,
                "sound_effects": True,
                "background_music": {
                    "enabled": True,
                    "type": "default",
                    "data": 2
                }
            },
            "profile": {
                "avatar": {
                    "type": "default",
                    "data": 1
                },
                "bio": "",
                "status": 1,
                "last_seen": 0
            },
            "security": {
                "email": None,
                "password": hashed_password,
                "mfa_secret": None,
                "mfa_recovery": None,
                "last_ip": None,
                "state": 0,
                "ratelimits": {
                    "authentication": 0,
                    "change_username": 0,
                    "change_password": 0,
                    "email_verification": 0,
                    "reset_password": 0,
                    "data_export": 0
                },
                "dormant": False,
                "locked_until": 0,
                "suspended_until": 0,
                "banned_until": 0,
                "delete_after": None,
                "deleted": False
            }
        })
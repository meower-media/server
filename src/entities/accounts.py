from passlib.hash import bcrypt
from pyotp import TOTP
from secrets import token_hex
import os

from src.util import status, uid, bitfield, flags
from src.entities import users
from src.database import db, redis

class Account:
    def __init__(
        self,
        _id: str,
        email: str = None,
        password: str = None,
        totp_secret: str = None,
        recovery_codes: list = None,
        flags: int = 0,
        last_updated: int = 0
    ):
        self.id = _id
        self.email = email
        self.password = password
        self.totp_secret = totp_secret
        self.recovery_codes = recovery_codes
        self.flags = flags
        self.last_updated = last_updated

    @property
    def client(self):
        return {
            "id": self.id,
            "email": self.email,
            "password_enabled": (self.password is not None),
            "mfa_methods": self.mfa_methods,
            "last_updated": int(self.last_updated.timestamp())
        }

    @property
    def mfa_enabled(self):
        return (len(self.mfa_methods) > 0)
    
    @property
    def mfa_methods(self):
        methods = []
        if self.totp_secret is not None:
            methods.append("totp")
        return methods

    @property
    def locked(self):
        return (redis.exists(f"lock:{self.id}") == 1)

    def check_password(self, password: str):
        if bcrypt.verify(password, self.password):
            return True
        else:
            try:
                pswd_attempts = int(redis.get(f"pswd_att:{self.id}").decode())
            except:
                pswd_attempts = 0

            if pswd_attempts == 4:
                redis.delete(f"pswd_att:{self.id}")
                redis.set(f"lock:{self.id}", "", ex=60)
            else:
                pswd_attempts += 1
                redis.set(f"pswd_att:{self.id}", str(pswd_attempts), ex=120)

            return False

    def change_password(self, password: str):
        self.password = bcrypt.hash(password, rounds=int(os.getenv("pswd_rounds", 12)))
        db.accounts.update_one({"_id": self._id}, {"$set": {"password": self.password}})

    def check_totp(self, code: str):
        if self.totp_secret is None:
            raise status.totpNotEnabled

        if redis.exists(f"totp:{self.id}:{code}") == 1:
            return False

        if code in self.recovery_codes:
            self.recovery_codes.remove(code)
            db.accounts.update_one({"_id": self.id}, {"$pull": {"recovery_codes": code}})
            return True
        elif TOTP(self.totp_secret).verify(code):
            redis.set(f"totp:{self.id}:{code}", "", ex=30)
            return True
        else:
            return False

    def enable_totp(self, secret: str, code: str):
        if self.totp_secret is not None:
            raise status.totpAlreadyEnabled

        if not TOTP(secret).verify(code):
            raise status.invalidTOTP

        if not self.mfa_enabled:
            self.regenerate_recovery_codes()
        self.totp_secret = secret
        db.accounts.update_one({"_id": self._id}, {"$set": {"totp_secret": self.totp_secret}})

    def disable_totp(self):
        if self.totp_secret is None:
            raise status.totpNotEnabled

        self.totp_secret = None
        db.accounts.update_one({"_id": self._id}, {"$set": {"totp_secret": self.totp_secret}})

    def regenerate_recovery_codes(self):
        self.recovery_codes = [token_hex(4) for i in range(8)]
        db.accounts.update_one({"_id": self.id}, {"$set": {"recovery_codes": self.recovery_codes}})

def create_account(username: str, password: str, child: bool, require_email: bool = False):
    if not users.username_available(username):
        raise status.alreadyExists

    user_flags = 0
    if child:
        user_flags = bitfield.add(user_flags, flags.user.child)
    if require_email:
        user_flags = bitfield.add(user_flags, flags.user.requireEmail)

    user = users.create_user(username, flags=user_flags)

    account = {
        "_id": user.id,
        "password": bcrypt.hash(password, rounds=int(os.getenv("pswd_rounds", 12))),
        "last_updated": uid.timestamp()
    }
    db.user_sync.insert_one({"_id": user.id})
    db.accounts.insert_one(account)

    return Account(**account)

def get_account(user_id: str):
    account = db.accounts.find_one({"_id": user_id})

    if account is None:
        raise status.notFound
    else:
        return Account(**account)

def get_id_from_email(email: str):
    user = db.accounts.find_one({"email": email.lower()}, projection={"_id": 1})

    if user is None:
        raise status.notFound
    else:
        return user["_id"]

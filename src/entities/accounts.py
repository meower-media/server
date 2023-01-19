from passlib.hash import bcrypt
from pyotp import TOTP
from secrets import token_hex
import os

from src.util import status, uid, bitfield
from src.entities import users
from src.database import db, redis

class Account:
    def __init__(
        self,
        _id: str,
        email: str = None,
        password: str = None,
        totp_secret: str = None,
        totp_recovery: list = None,
        flags: int = 0,
        last_updated: int = 0
    ):
        self.id = _id
        self.email = email
        self.password = password
        self.totp_secret = totp_secret
        self.totp_recovery = totp_recovery
        self.flags = flags
        self.last_updated = last_updated

    @property
    def require_mfa(self):
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

    def check_totp(self, code: str):
        if self.totp_secret is None:
            raise status.totpNotEnabled

        if code in self.totp_recovery:
            self.totp_recovery.remove(code)
            db.accounts.update_one({"_id": self._id}, {"$pull": {"totp_recovery": code}})
            return True
        elif TOTP(self.totp_secret).verify(code) and (redis.get(f"totp:{self._id}:{code}") is None):
            redis.set(f"totp:{self._id}:{code}", "", ex=30)
            return True
        else:
            return False

    def change_password(self, password: str):
        self.password = bcrypt.hash(password, rounds=int(os.getenv("pswd_rounds", 12)))
        db.accounts.update_one({"_id": self._id}, {"$set": {"password": self.password}})
        return status.ok

    def add_totp(self, secret: str, code: str):
        if self.totp_secret is not None:
            raise status.totpAlreadyEnabled

        if not TOTP(secret).verify(code):
            raise status.invalidTOTP

        self.totp_secret = secret
        self.totp_recovery = [(token_hex(2) + "-" + token_hex(2)) for i in range(8)]
        db.accounts.update_one({"_id": self._id}, {"$set": {"totp_secret": self.totp_secret, "totp_recovery": self.totp_recovery}})
        return status.ok

    def remove_totp(self):
        if self.totp_secret is None:
            raise status.totpNotEnabled

        self.totp_secret = None
        self.totp_recovery = None
        db.accounts.update_one({"_id": self._id}, {"$set": {"totp_secret": self.totp_secret, "totp_recovery": self.totp_recovery}})
        return status.ok

def create_account(username: str, password: str, child: bool):
    if not users.username_available(username):
        raise status.alreadyExists

    if child:
        flags = bitfield.create([flags.user.child])
    else:
        flags = bitfield.create([])
    user = users.create_user(username, flags=flags)

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

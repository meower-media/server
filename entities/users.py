import bcrypt, time
from pymongo import collation
from typing import Optional, Literal

import models, errors
from entities import ids
from database import db


USERNAME_REGEX = "[a-zA-Z0-9-_]{1,20}"
BCRYPT_SALT_ROUNDS = 14


def db_to_v0(user: models.db.User, include_private: bool) -> models.v0.User:
    _user = {
        "_id": user["username"],
        "uuid": str(user["_id"]),
        "lower_username": user["username"].lower(),
        "flags": user.get("flags", 0),
        "permissions": user.get("permissions", 0),
        "lvl": 0,
        "banned": True if
            user["ban"].get("state") == "perm_ban" or \
            (
                user["ban"].get("state") == "temp_ban" and \
                user["ban"].get("expires") > int(time.time())
            )
        else False,
        "avatar": user.get("avatar", ""),
        "avatar_color": user.get("color", "000000"),
        "pfp_data": user.get("legacy_avatar", 2),
        "quote": user.get("quote", ""),
        "created": 0,
        "last_seen": user.get("last_seen", 0)
    }
    if include_private:
        _user.update({
            "email": user.get("email"),
            "ban": user.get("ban"),
            "delete_after": user.get("delete_after")
        })
    return _user

def min_db_to_v0(min_user: models.db.MinUser) -> models.v0.MinUser:
    return {
        "_id": min_user["username"],
        "uuid": str(min_user["_id"]),
        "flags": min_user.get("flags", 0),
        "avatar": min_user.get("avatar", ""),
        "avatar_color": min_user.get("color", "000000"),
        "pfp_data": min_user.get("legacy_avatar", 2)
    }

def ban_db_to_v0(ban: models.db.UserBan) -> models.v0.UserBan:
    return {
        "state": ban.get("state", "none"),
        "restrictions": ban.get("restrictions", 0),
        "expires": ban.get("expires", 0),
        "reason": ban.get("reason", "")
    }

def create_user(username: str, password: str) -> models.db.User:
    if username_taken(username):
        raise errors.UsernameExists
    user: models.db.User = {
        "_id": ids.gen_id(),
        "username": username,
        "password": hash_password(password),
        "ban": {},
        "settings": {}
    }
    db.users.insert_one(user)
    return user

def username_taken(username: str) -> bool:
    return db.users.count_documents(
        {"username": username},
        collation=collation.Collation(
            locale="en_US",
            strength=2,
        ),
        limit=1,
    ) > 0

def get_user(user_id: int) -> models.db.User:
    user: models.db.User = db.users.find_one({"_id": user_id})
    if user:
        return user
    else:
        raise errors.UserNotFound

def get_min_user(user_id: int) -> models.db.MinUser:
    user: models.db.MinUser = db.users.find_one({"_id": user_id}, projection={
        "_id": 1,
        "username": 1,
        "flags": 1,
        "avatar": 1,
        "legacy_avatar": 1,
        "color": 1
    })
    if user:
        return user
    else:
        raise errors.UserNotFound

def get_user_by_username(username: str) -> models.db.User:
    user: models.db.User = db.users.find_one(
        {"username": username},
        collation=collation.Collation(
            locale="en_US",
            strength=2,
        ),
    )
    if user:
        return user
    else:
        raise errors.UserNotFound

def get_user_by_email(email: str) -> models.db.User:
    user: models.db.User = db.users.find_one({"email": email})
    if user:
        return user
    else:
        raise errors.UserNotFound

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt(rounds=BCRYPT_SALT_ROUNDS)
    ).decode()

def check_password_hash(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed_password.encode())

def edit_profile(
    user_id: int,
    username: Optional[str] = None,
    avatar: Optional[str] = None,
    legacy_avatar: Optional[int] = None,
    color: Optional[str] = None,
    quote: Optional[str] = None
):
    _set = {}
    if username is not None:
        if username_taken(username):
            raise errors.UsernameExists
        _set["username"] = username
    if avatar is not None:
        _set["avatar"] = avatar
    if legacy_avatar is not None:
        _set["legacy_avatar"] = legacy_avatar
    if color is not None:
        _set["color"] = color
    if quote is not None:
        _set["quote"] = quote
    db.users.update_one({"_id": user_id}, {"$set": _set})

def send_email_verification(user_id: int, email_address: str):
    pass

def change_email_address(user_id: int, email_address: str):
    db.users.update_one({"_id": user_id}, {"$set": {
        "email": email_address
    }})

def send_password_reset_email(user_id: int, email_address: str):
    pass

def change_password(user_id: int, new_password: str):
    db.users.update_one({"_id": user_id}, {"$set": {
        "password": bcrypt.hashpw(
            new_password.encode(),
            bcrypt.gensalt(rounds=BCRYPT_SALT_ROUNDS)
        ).decode()
    }})

def change_flags(user_id: int, new_flags: int):
    db.users.update_one({"_id": user_id}, {"$set": {"flags": new_flags}})

def change_permissions(user_id: int, new_permissions: int):
    db.users.update_one({"_id": user_id}, {"$set": {"permissions": new_permissions}})

def ban_user(
    user_id: int,
    state: Optional[Literal[
        "none",
        "temp_restriction",
        "perm_restriction",
        "temp_ban",
        "perm_ban"  
    ]],
    restrictions: Optional[int],
    expires: Optional[int],
    reason: Optional[str]
):
    # Get current ban
    current_ban = db.users.find_one({"_id": user_id}, projection={
        "ban.state": 1,
        "ban.restrictions": 1,
        "ban.expires": 1,
        "ban.reason": 1
    })["ban"]
    
    # Create new ban
    new_ban = {
        "state": state if state is not None else current_ban.get("state", "none"),
        "restrictions": restrictions if restrictions is not None else current_ban.get("restrictions", 0),
        "expires": expires if expires is not None else current_ban.get("expires", 0),
        "reason": reason if reason is not None else current_ban.get("reason", "")
    }

    # Update ban
    db.users.update_one({"_id": user_id}, {"$set": {"ban": new_ban}})

def get_client_settings(user_id: int, origin: str) -> dict:
    settings = db.client_settings.find_one({"_id": {
        "user_id": user_id,
        "origin": origin
    }})
    if settings:
        del settings["_id"]
        return settings
    else:
        return {}

def update_client_settings(user_id: int, origin: str, new_data: dict):
    db.client_settings.update_one({"_id": {
        "user_id": user_id,
        "origin": origin
    }}, {"$set": new_data}, upsert=True)
    pass

def update_last_seen(user_id: int):
    db.users.update_one({"_id": user_id}, {"$set": {
        "last_seen": int(time.time())
    }})

def delete_user(user_id: int, delay: int = 0):
    db.users.update_one({"_id": user_id}, {"$set": {
        "delete_after": int(time.time())+delay
    }})

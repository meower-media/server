from copy import copy
from datetime import datetime
import time
import string

from src.util import status, uid, events, bitfield, flags
from src.database import db

SERVER = {
    "_id": "0",
    "username": "Server",
    "lower_username": "server",
    "flags": bitfield.create([flags.user.system]),
    "created": uid.timestamp(epoch=0),
    "badges": ["MEOWY"]
}

DELETED = {
    "_id": "1",
    "username": "Deleted",
    "lower_username": "deleted",
    "flags": bitfield.create([flags.user.deleted]),
    "created": uid.timestamp(epoch=0)
}

MEOWER = {
    "_id": "2",
    "username": "Meower",
    "lower_username": "meower",
    "flags": bitfield.create([flags.user.system]),
    "created": uid.timestamp(epoch=0),
    "badges": ["MEOWY"]
}

PERMITTED_CHARS_USERNAME = set(string.ascii_letters + string.digits + "_-.")

CONFIG_KEYS = {
    "theme": dict,
    "sfx": bool,
    "bgm": bool,
    "bgm_song": int,
    "debug": bool
}

class User:
    def __init__(
        self,
        _id: str,
        username: str,
        lower_username: str,
        theme: dict = {},
        flags: int = 0,
        admin: int = 0,
        created: datetime = None,
        icon: dict = {"type": 0, "data": 2},
        quote: str = "",
        badges: list = [],
        stats: dict = {"followers": 0, "following": 0},
        redirect_to: str = None,
        delete_after: datetime = None
    ):
        self.id = _id
        self.username = username
        self.lower_username = lower_username
        self.flags = flags
        self.admin = admin
        self.created = created
        self.theme = theme
        self.icon = icon
        self.quote = quote
        self.badges = badges
        self.stats = stats
        self.redirect_to = redirect_to
        self.delete_after = delete_after

        if self.redirect_to is not None:
            self = get_user(self.redirect_to)

    @property
    def public(self):
        return {
            "id": self.id,
            "username": self.username,
            "flags": self.public_flags,
            "created": int(self.created.timestamp()),
            "theme": self.theme,
            "icon": self.icon,
            "quote": self.quote,
            "stats": self.stats,
            "badges": self.badges
        }

    @property
    def client(self):
        return {
            "id": self.id,
            "username": self.username,
            "flags": self.flags,
            "admin": self.admin,
            "created": self.created,
            "theme": self.theme,
            "icon": self.icon,
            "quote": self.quote,
            "stats": self.stats,
            "badges": self.badges
        }

    @property
    def legacy(self):
        return {
            "_id": self.username,
            "lower_username": self.lower_username,
            "created": int(self.created.timestamp()),
            "uuid": self.id,
            "pfp_data": (self.icon["data"] if (self.icon["type"] == 0) else 2),
            "quote": self.quote,
            "lvl": 0,
            "banned": False
        }

    @property
    def partial(self):
        return {
            "id": self.id,
            "username": self.username,
            "flags": self.public_flags,
            "icon": self.icon
        }

    @property
    def public_flags(self):
        pub_flags = copy(self.flags)
        for flag in [
            flags.user.child,
            flags.user.ageNotConfirmed,
            flags.user.requireEmail,
            flags.user.requireMFA
        ]:
            pub_flags = bitfield.remove(pub_flags, flag)
        return pub_flags

    def count_stats(self):
        followers = db.followed_users.count_documents({"to": self.id})
        following = db.followed_users.count_documents({"from": self.id})
        self.stats = {"followers": followers, "following": following}
        db.users.update_one({"_id": self.id}, {"$set": {"stats": self.stats}})
        events.emit_event("user_updated", {
            "id": self.id,
            "stats": self.stats
        })

    def get_following(self):
        return [relationship["to"] for relationship in db.followed_users.find({"from": self.id})]

    def get_blocked(self):
        return [relationship["to"] for relationship in db.blocked_users.find({"from": self.id})]

    def is_following(self, user):
        return (db.followed_users.find_one({"to": user.id, "from": self.id}, projection={"_id": 1}) is not None)
    
    def is_followed(self, user):
        return (db.followed_users.find_one({"to": self.id, "from": user.id}, projection={"_id": 1}) is not None)

    def is_blocked(self, user):
        return (db.blocked_users.find_one({"$or": [{"to": user.id, "from": self.id}, {"to": self.id, "from": user.id}]}, projection={"_id": 1}) is not None)

    def follow_user(self, user):
        if self.is_blocked(user):
            raise status.missingPermissions  # placeholder
        if self.is_following(user):
            raise status.missingPermissions  # placeholder
        
        db.followed_users.insert_one({
            "_id": uid.snowflake(),
            "to": user.id,
            "from": self.id,
            "time": uid.timestamp()
        })

    def unfollow_user(self, user):
        db.followed_users.delete_one({"to": user.id, "from": self.id})

    def remove_follower(self, user):
        db.followed_users.delete_one({"to": self.id, "from": user.id})

    def block_user(self, user):
        if db.blocked_users.find_one({"to": user.id, "from": self.id}, projection={"_id": 1}) is not None:
            raise status.missingPermissions  # placeholder
        
        self.unfollow_user(user)
        self.remove_follower(user)

        db.blocked_users.insert_one({
            "_id": uid.snowflake(),
            "to": user.id,
            "from": self.id,
            "time": uid.timestamp()
        })

    def unblock_user(self, user):
        db.blocked_users.delete_one({"to": user.id, "from": self.id})

    @property
    def username_history(self):
        return list(db.username_history.find({"user_id": self._id}, projection={"_id": 0, "user_id": 0}, sort=[("_id", -1)]))

    def update_username(self, username: str, by_admin: bool = False, store_history: bool = True):
        if not username_available(username):
            raise status.alreadyExists

        # Add old username to username history
        if store_history:
            db.username_history.insert_one({
                "_id": uid.snowflake(),
                "user_id": self.id,
                "old_username": self.username,
                "new_username": username,
                "by_admin": by_admin,
                "time": int(time.time())
            })

        # Update current user
        self.username = username
        self.lower_username = username.lower()
        db.users.update_one({"_id": self.id}, {"$set": {
            "username": self.username,
            "lower_username": self.lower_username
        }})
        events.emit_event("user_updated", {
            "id": self.id,
            "username": self.username
        })

def create_user(username: str, flags: int = 0):
    userdata = {
        "_id": uid.snowflake(),
        "username": username,
        "lower_username": username.lower(),
        "flags": flags,
        "created": uid.timestamp()
    }
    db.users.insert_one(userdata)
    return User(**userdata)

def get_user(user_id: str, return_deleted: bool = True):
    if user_id == "0":
        user = SERVER
    elif user_id == "1":
        user = DELETED
    elif user_id == "2":
        user = MEOWER
    else:
        user = db.users.find_one({"_id": user_id})
        if (user is None) and return_deleted:
            user = DELETED

    if user is None:
        raise status.notFound
    else:
        return User(**user)

def username_available(username: str):
    if username.lower() in ["server", "deleted", "meower"]:
        return False

    return (db.users.find_one({"lower_username": username.lower()}, projection={"_id": 1}) is None)

def get_id_from_username(username: str):
    user = db.users.find_one({"lower_username": username.lower()}, projection={"_id": 1})

    if user is None:
        raise status.notFound
    else:
        return user["_id"]

def search_users(query: str, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all users
    return [User(**user) for user in db.users.find({"$text": {"$search": query}, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

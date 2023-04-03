from copy import copy
from base64 import b64encode, b64decode
import bcrypt
import time
import ujson
import re

from src.common.entities import posts, chats, reports, audit_log
from src.common.util import uid, regex, errors, security, events
from src.common.database import db, redis, count_pages


CONFIG_KEYS = {
    "invisible": bool,
    "unread_inbox": bool,
    "accepting_invites": bool,
    "theme": str,
    "mode": bool,
    "layout": str,
    "debug": bool,
    "sfx": bool,
    "bgm": bool,
    "bgm_song": int,
    "pfp_data": int,
    "quote": str
}


# Default users
SERVER = {
    "_id": "Server",
    "lower_username": "server",
    "uuid": "0",
    "created": 0
}
DELETED = {
    "_id": "Deleted",
    "lower_username": "deleted",
    "uuid": "1",
    "created": 0
}
MEOWER = {
    "_id": "Meower",
    "lower_username": "meower",
    "uuid": "2",
    "created": 0
}


class User:
    def __init__(
        self,
        _id: str,
        lower_username: str,
        uuid: str,
        created: int,
        delete_after: int = None,
        email: str = None,
        pswd: str = None,
        token_version: int = 0,
        lvl: int = 0,
        report_reputation: float = 0,
        last_ip: str = None,
        banned_until: int = None,
        invisible: bool = False,
        unread_inbox: bool = False,
        accepting_invites: bool = True,
        theme: str = "orange",
        mode: bool = True,
        layout: str = "new",
        debug: bool = False,
        sfx: bool = True,
        bgm: bool = True,
        bgm_song: int = 2,
        pfp_data: int = 1,
        quote: str = ""
    ):
        self.username = _id
        self.lower_username = lower_username
        self.uuid = uuid
        self.created = created
        self.delete_after = delete_after
        self.email = email
        self.pswd = pswd
        self.token_version = token_version
        self.lvl = lvl
        self.report_reputation = report_reputation
        self.last_ip = last_ip
        self.banned_until = banned_until
        self.invisible= invisible
        self.unread_inbox = unread_inbox
        self.accepting_invites = accepting_invites
        self.theme = theme
        self.mode = mode
        self.layout = layout
        self.debug = debug
        self.sfx = sfx
        self.bgm = bgm
        self.bgm_song = bgm_song
        self.pfp_data = pfp_data
        self.quote = quote

    @property
    def public(self):
        return {
            "_id": self.username,
            "lower_username": self.lower_username,
            "uuid": self.uuid,
            "created": self.created,
            "lvl": self.lvl,
            "banned": self.banned,
            "pfp_data": self.pfp_data,
            "quote": self.quote
        }
    
    @property
    def client(self):
        return {
            "_id": self.username,
            "lower_username": self.lower_username,
            "uuid": self.uuid,
            "created": self.created,
            "delete_after": (self.delete_after if self.delete_after else None),
            "email": self.email,
            "lvl": self.lvl,
            "report_reputation": self.report_reputation,
            "banned": self.banned,
            "invisible": self.invisible,
            "unread_inbox": self.unread_inbox,
            "accepting_invites": self.accepting_invites,
            "theme": self.theme,
            "mode": self.mode,
            "layout": self.layout,
            "debug": self.debug,
            "sfx": self.sfx,
            "bgm": self.bgm,
            "bgm_song": self.bgm_song,
            "pfp_data": self.pfp_data,
            "quote": self.quote
        }

    @property
    def banned(self):
        if not isinstance(self.banned_until, int):
            return False
        elif (self.banned_until == -1) or (self.banned_until > time.time()):
            return True
        else:
            return False

    def update_config(self, new_config: dict):
        # Update config keys
        for key, value in copy(new_config).items():
            if key not in CONFIG_KEYS:
                del new_config[key]
            elif not isinstance(value, CONFIG_KEYS[key]):
                del new_config[key]
            elif isinstance(value, str) and (len(value) > 360):
                del new_config[key]
            elif isinstance(value, int) and (value > 255):
                del new_config[key]
            else:
                setattr(self, key, value)
        db.users.update_one({"_id": self.username}, {"$set": new_config})

        # Delete cache
        redis.delete(f"user:{self.username}")

        # Send config update event
        events.send_event("update_config", self.client)

    def change_username(self, new_username: str) -> bool:
        # Check if new username is available
        if not username_exists(new_username, case_sensitive=False):
            raise errors.AlreadyExists

        # Get old username
        old_username = copy(self.username)

        # Create new user
        db.users.insert_one({
            "_id": new_username,
            "lower_username": new_username.lower(),
            "uuid": self.uuid,
            "created": self.created,
            "delete_after": self.delete_after,
            "email": self.email,
            "pswd": self.pswd,
            "token_key": self.token_key,
            "lvl": self.lvl,
            "report_reputation": self.report_reputation,
            "last_ip": self.last_ip,
            "banned_until": self.banned_until,
            "invisible": self.invisible,
            "unread_inbox": self.unread_inbox,
            "accepting_invites": self.accepting_invites,
            "theme": self.theme,
            "mode": self.mode,
            "layout": self.layout,
            "debug": self.debug,
            "sfx": self.sfx,
            "bgm": self.bgm,
            "bgm_song": self.bgm_song,
            "pfp_data": self.pfp_data,
            "quote": self.quote
        })

        # Update attributes
        self.username = new_username
        self.lower_username = new_username.lower()

        # Update all networks
        db.networks.update_many({"users": old_username}, {"$set": {"users.$": self.username}})

        # Update all posts
        db.posts.update_many({"origin": old_username}, {"$set": {"origin": self.username}})

        # Update all chats
        db.chats.update_many({"members": old_username}, {"$set": {"members.$": self.username}})
        db.chats.update_many({"members": old_username, "owner": old_username}, {"$set": {"owner": self.username}})

        # Update report
        report = db.reports.find_one({"_id": old_username})
        if report:
            report["_id"] = self.username
            db.reports.insert_one(report)
            db.reports.delete_one({"_id": old_username})

        # Delete old user
        db.users.delete_one({"_id": old_username})

        # Delete cache
        redis.delete(f"user:{old_username}")
        redis.delete(f"user:{self.username}")

        # Kick old user
        events.send_event("kick_user", {"username": old_username})

    def check_password(self, password: str) -> bool:
        # Check if user is waiting to be deleted
        if self.delete_after and (self.delete_after <= time.time()):
            return False

        return bcrypt.checkpw(password.encode(), self.pswd.encode())
    
    def change_password(self, new_password: str):
        # Set new password
        self.pswd = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(12)).decode()
        db.users.update_one({"_id": self.username}, {"$set": {"pswd": self.pswd}})

        # Delete cache
        redis.delete(f"user:{self.username}")

    def generate_token(self) -> str:
        # Generate data
        data = b64encode(f"{self.uuid}:{self.token_version}:{str(time.time())}".encode())

        # Generate new signature
        signature = security.sign_data(data)

        # Return token
        return f"{data.decode()}.{signature.decode()}"

    def validate_token(self, token: str) -> bool:
        # Decode token
        try:
            data, signature = token.split(".")
        except:
            return False

        # Check data properties
        try:
            user_uuid, version, timestamp = b64decode(data.encode()).decode().split(":")
            version = int(version)
            timestamp = float(timestamp)
        except:
            return False
        else:
            if (user_uuid != self.uuid) or (version != self.token_version):
                return False

        # Check token signature
        return security.validate_signature(signature.encode(), data.encode())

    def revoke_sessions(self):
        # Increment token version
        self.token_version += 1
        db.users.update_one({"_id": self.username}, {"$set": {"token_version": self.token_version}})

        # Delete cache
        redis.delete(f"user:{self.username}")

        # Kick user
        events.send_event("kick_user", {"username": self.username})

    def set_level(self, level: int):
        # Set user level
        self.lvl = level
        db.users.update_one({"_id": self.username}, {"$set": {"lvl": self.lvl}})

        # Delete cache
        redis.delete(f"user:{self.username}")

        # Send config update event
        events.send_event("update_config", self.client)

    def clear_posts(self, moderator: str = None):
        # Delete posts
        for post in db.posts.find({"author": self.username}):
            posts.Post(**post).delete(moderator)

        # Create audit log item
        if moderator:
            audit_log.create_log("clear_user_posts", moderator, {
                "username": self.username
            })

    def alert(self, content: str, moderator: str = None):
        # Create inbox message
        posts.create_inbox_message(self.username, f"Message from a moderator: {content}")

        # Close report
        reports.close_report(self.username, True, moderator)

        # Create audit log item
        if moderator:
            audit_log.create_log("alert_user", moderator, {
                "username": self.username,
                "content": content
            })

    def kick(self, moderator: str = None):
        # Kick user
        events.send_event("kick_user", {
            "username": self.username,
            "code": "Kicked"
        })

        # Close report
        reports.close_report(self.username, True, moderator)

        # Create audit log item
        if moderator:
            audit_log.create_log("kick_user", moderator, {"username": self.username})

    def ban(self, expires: int = -1, moderator: str = None):
        # Set ban status
        self.banned_until = expires
        db.users.update_one({"_id": self.username}, {"$set": {"banned_until": self.banned_until}})

        # Delete cache
        redis.delete(f"user:{self.username}")

        # Send config update event
        events.send_event("update_config", self.client)

        # Close report
        reports.close_report(self.username, True, moderator)

        # Create audit log item
        if moderator:
            audit_log.create_log("ban_user", moderator, {
                "username": self.username,
                "expires": expires
            })

    def unban(self, moderator: str = None):
        # Set ban status
        self.banned_until = None
        db.users.update_one({"_id": self.username}, {"$set": {"banned_until": self.banned_until}})

        # Delete cache
        redis.delete(f"user:{self.username}")

        # Send config update event
        events.send_event("update_config", self.client)

        # Create audit log item
        if moderator:
            audit_log.create_log("pardon_user", moderator, {
                "username": self.username
            })

    def terminate(self, moderator: str = None):
        # Ban user
        self.ban(moderator=moderator)

        # Clear posts
        self.clear_posts(moderator=moderator)

        # Schedule account for deletion (14 days)
        self.schedule_deletion(delay=2592000)

        # Create audit log item
        if moderator:
            audit_log.create_log("terminate_user", moderator, {
                "username": self.username
            })

    def schedule_deletion(self, delay: int = 259200):
        # Set deletion delay (72 hours default)
        self.delete_after = int(time.time()+delay)
        db.users.update_one({"_id": self.username}, {"$set": {"delete_after": self.delete_after}})

        # Revoke sessions
        self.revoke_sessions()

        # Delete cache
        redis.delete(f"user:{self.username}")

        # Kick user
        events.send_event("kick_user", {"username": self.username})

    def cancel_scheduled_deletion(self, send_inbox_message: bool = True):
        # Reset deletion timestamp
        self.delete_after = None
        db.users.update_one({"_id": self.username}, {"$unset": {"delete_after": ""}})

        # Delete cache
        redis.delete(f"user:{self.username}")

        # Send inbox message telling the user the deletion was cancelled
        if send_inbox_message:
            posts.create_inbox_message(self.username, f"Your account was scheduled for deletion but you logged back in. Your account is no longer scheduled for deletion!")

    def delete(self):
        # Update all networks
        db.networks.update_many({"users": self.username}, {"$pull": {"users": self.username}})

        # Delete all posts
        db.posts.delete_many({"author": self.username})

        # Update all chats
        _, user_chats = chats.get_users_chats(self.username, page=None)
        for chat in user_chats:
            chat.remove_member(self.username)

        # Close report
        reports.close_report(self.username, None)

        # Delete user
        db.users.delete_one({"_id": self.username})

        # Delete cache
        redis.delete(f"user:{self.username}")

        # Kick user
        events.send_event("kick_user", {"username": self.username})


def username_exists(username: str, case_sensitive: bool = True) -> bool:
    if (case_sensitive and (username in {"Server", "Deleted", "Meower"})) or ((not case_sensitive) and (username.lower() in {"server", "deleted", "meower"})):
        return True
    elif redis.exists(f"user:{username}") == 1:
        return True
    elif case_sensitive:
        return (db.users.count_documents({"_id": username}) > 0)
    else:
        return (db.users.count_documents({"lower_username": username.lower()}) > 0)


def create_user(username: str, password: str) -> User:
    # Check if username is valid
    if not re.fullmatch(regex.USERNAME_VALIDATION, username):
        raise errors.IllegalCharacters

    # Check if username is available
    if username_exists(username, case_sensitive=False):
        raise errors.AlreadyExists

    # Create user data
    user_data = {
        "_id": username,
        "lower_username": username.lower(),
        "uuid": uid.uuid(),
        "created": int(time.time()),
        "pswd": bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    }

    # Insert user into database
    db.users.insert_one(user_data)

    # Add user to cache
    redis.set(f"user:{username}", ujson.dumps(user_data), ex=120)
    
    # Send welcome inbox message
    posts.create_inbox_message(username, "Welcome to Meower! We welcome you with open arms! You can get started by making friends in the global chat or home, or by searching for people and adding them to a group chat. We hope you have fun!")

    # Return user object
    return User(**user_data)


def get_user(username: str) -> User:
    if username == "Server":
        return User(**SERVER)
    elif username == "Deleted":
        return User(**DELETED)
    elif username == "Meower":
        return User(**MEOWER)
    else:
        # Get user from cache
        user_data = redis.get(f"user:{username}")
        if user_data:
            user_data = ujson.loads(user_data)

        # Get user from database and add to cache
        if not user_data:
            user_data = db.users.find_one({"_id": username})
            if user_data:
                redis.set(f"user:{username}", ujson.dumps(user_data), ex=120)

        # Return user object
        if user_data:
            return User(**user_data)
        else:
            raise errors.NotFound


def search_users(username_query: str, page: int = 1) -> list[User]:
    query = {
        "$text": {"$search": username_query.lower()}
    }
    return count_pages("users", query), [User(**user) for user in db.users.find(query,
                                                     sort=[("created", -1)],
                                                     skip=((page-1)*25),
                                                     limit=25)]

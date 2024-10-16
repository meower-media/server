from typing import Optional, TypedDict
import pymongo.collation, re, msgpack

from database import db, rdb
from meowid import gen_id, extract_id
from accounts import Account
import errors


USERNAME_REGEX = "[a-zA-Z0-9-_]{1,20}"
SYSTEM_USER_USERNAMES = {"server", "deleted", "meower", "admin", "username"}
MIN_USER_PROJECTION = {
    "permissions": 0,
    "quote": 0,
    "last_seen_at": 0
}


class UserFlags:
    SYSTEM = 1
    DELETED = 2
    PROTECTED = 4
    POST_RATELIMIT_BYPASS = 8
    REQUIRE_EMAIL = 16  # not used yet
    LOCKED = 32


class AdminPermissions:
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
    CLEAR_PROFILE_DETAILS = 1024
    VIEW_BAN_STATES = 2048
    EDIT_BAN_STATES = 4096
    DELETE_USERS = 8192

    VIEW_IPS = 16384
    BLOCK_IPS = 32768

    VIEW_CHATS = 65536
    EDIT_CHATS = 131072

    SEND_ANNOUNCEMENTS = 262144


class UserDB(TypedDict):
    _id: int
    username: str
    redirect_to: Optional[int]

    flags: Optional[int]
    permissions: Optional[int]

    legacy_icon: Optional[int]
    icon: Optional[str]
    color: Optional[str]
    quote: Optional[str]

    settings: Optional[bytes]

    last_seen_at: Optional[int]


class UserV0(TypedDict):
    _id: str  # username
    uuid: str  # MeowID
    created: Optional[int]  # creation timestamp

    pfp_data: int  # legacy icon
    avatar: str  # icon
    avatar_color: str  # color
    quote: Optional[str]

    flags: Optional[int]
    permissions: Optional[int]
    banned: Optional[bool]

    last_seen: Optional[int]


class User:
    def __init__(self, data: UserDB):
        self.id = data["_id"]
        self.username = data["username"]
        
        self.flags = data.get("flags", 0)
        self.permissions = data.get("permissions", 0)

        self.legacy_icon = data.get("legacy_icon", 1)
        self.icon = data.get("icon", "")
        self.color = data.get("color", "000000")
        self.quote = data.get("quote", "")

        if data.get("settings"):
            self.settings = msgpack.unpackb(data["settings"])
        else:
            self.settings = {}

        self.last_seen_at = data.get("last_seen_at")

    @classmethod
    async def create_account(cls: "User", username: str, password: str) -> tuple[Account, "User"]:
        # Check username
        if not re.fullmatch(USERNAME_REGEX, username):
            raise errors.UsernameDisallowed
        if cls.username_taken(username):
            raise errors.UsernameTaken

        # Make sure password meets requirements
        if len(password) < 8 or len(password) > 72:
            raise errors.PasswordDisallowed

        # Generate user ID
        user_id = await gen_id()

        # Create user
        data: UserDB = {
            "_id": user_id,
            "username": username
        }
        db.users.insert_one(data)

        # Create account
        account = Account.create(user_id, password)

        # Send welcome message
        rdb.publish("admin", msgpack.packb({
            "op": "alert_user",
            "user": user_id,
            "content": "Welcome to Meower! We welcome you with open arms! You can get started by making friends in the global chat or home, or by searching for people and adding them to a group chat. We hope you have fun!"
        }))

        return account, cls(data)

    @classmethod
    def get_by_id(cls: "User", user_id: int, min: bool = False) -> "User":
        data: Optional[UserDB] = db.users.find_one({"_id": user_id}, projection=MIN_USER_PROJECTION if min else None)
        if not data:
            raise errors.UserNotFound
        return cls(data)
    
    @classmethod
    def get_by_username(cls: "User", username: str, allow_redirects: bool = True) -> "User":
        data: Optional[UserDB] = db.users.find_one({
            "username": username
        }, collation=pymongo.collation.Collation("en_US", False))
        if not data:
            raise errors.UserNotFound
        
        redirect_to = data.get("redirect_to")
        if redirect_to and allow_redirects:
            return cls.get_by_id(redirect_to)

        return cls(data)

    @staticmethod
    def username_taken(username: str) -> bool:
        if username.lower() in SYSTEM_USER_USERNAMES:
            return True
        return db.users.count_documents({
            "username": username
        }, limit=1, collation=pymongo.collation.Collation("en_US", False)) > 0

    @property
    def v0(self) -> UserV0:
        created, _, _ = extract_id(self.id)

        banned = False

        return {
            **self.v0_min,
            "created": created,
            "quote": self.quote,
            "permissions": self.permissions,
            "banned": banned,
            "last_seen": self.last_seen_at
        }

    @property
    def v0_min(self) -> UserV0:
        return {
            "_id": self.username,
            "uuid": str(self.id),

            "pfp_data": self.legacy_icon,
            "avatar": self.icon,
            "avatar_color": self.color,
            
            "flags": self.flags
        }

    @property
    def account(self) -> Account:
        return Account.get_by_id(self.id)

    def has_permission(self, permission: int) -> bool:
        if ((self.permissions & AdminPermissions.SYSADMIN) == AdminPermissions.SYSADMIN):
            return True
        else:
            return ((self.permissions & permission) == permission)

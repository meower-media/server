from datetime import datetime
import json

from src.util import uid, bitfield, flags
from src.entities import users, networks, security_cookies
from src.database import db, redis

READ_ONLY_MODE = bitfield.create([
    flags.suspension.createPosts,
    flags.suspension.meowPosts,
    flags.suspension.sendMessages,
    flags.suspension.editProfile,
    flags.suspension.uploadFiles
])

class Suspension:
    def __init__(
        self,
        _id: str,
        user_id: str = None,
        moderator_id: str = None,
        evaded_from: str = None,
        possible_alt_ids: list = [],
        exempt_alt_ids: list = [],
        features: int = 0,
        reason: str = None,
        poisonous: bool = False,
        status: int = 0,  # 0: standard, 1: block appeals, 2: appeal pending review, 3: staff waiting for more info, 4: overturned, 5: upheld
        started: datetime = None,
        expires: datetime = None
    ):
        self.id = _id
        self.user_id = user_id
        self.moderator_id = moderator_id
        self.evaded_from = evaded_from
        self.possible_alt_ids = possible_alt_ids
        self.exempt_alt_ids = exempt_alt_ids
        self.features = features
        self.reason = reason
        self.poisonous = poisonous
        self.status = status
        self.started = started
        self.expires = expires

    @property
    def user(self):
        return users.get_user(self.user_id)
    
    @property
    def moderator(self):
        return users.get_user(self.moderator_id)

    @property
    def possible_alts(self):
        return [users.get_user(alt_id) for alt_id in self.possible_alt_ids]
    
    @property
    def exempt_alts(self):
        return [users.get_user(alt_id) for alt_id in self.exempt_alt_ids]

    @property
    def active(self):
        if self.status == 4:
            return False
        elif (self.expires is not None) and (self.expires < uid.timestamp()):
            return False
        else:
            return True

    @property
    def client(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "features": self.features,
            "reason": self.reason,
            "status": self.status,
            "started": int(self.started.timestamp()),
            "expires": int(self.expires.timestamp())
        }

    @property
    def admin(self):
        return {
            "id": self.id,
            "user": self.user.partial,
            "moderator": self.moderator.partial,
            "suspended_features": self.suspended_features,
            "reason": self.reason,
            "alts": [user.partial for user in self.alts],
            "poisoned_ips": self.poisoned_ips,
            "poison_devices": self.poison_devices,
            "poison_ips": self.poison_ips,
            "revoked": self.revoked,
            "appeal_status": self.appeal_status,
            "started": int(self.started.timestamp()),
            "expires": (None if self.expires is None else int(self.expires.timestamp()))
        }

    def get_appeal_messages(self):
        return [AppealMessage(**message) for message in db.appeal_messages.find({"suspension_id": self.id}, sort=[("_id", -1)])]

    def send_appeal_message(self, author: users.User, content: str):
        message = {
            "_id": uid.snowflake(),
            "suspension_id": self.id,
            "author_id": author.id,
            "content": content,
            "time": uid.timestamp()
        }

        db.appeal_messages.insert_one(message)
        message = AppealMessage(**message)
        return message

    def edit(self, features: int = None, reason: str = None, poisonous: bool = None, status: int = None):
        if features is not None:
            self.features = features
        if reason is not None:
            self.reason = reason
        if poisonous is not None:
            self.poisonous = poisonous
        if status is not None:
            self.status = status
        
        db.suspensions.update_one({"_id": self.id}, {"$set": {
            "features": self.features,
            "reason": self.reason,
            "poisonous": self.poisonous,
            "status": self.status
        }})
        redis.publish("meower:cl", json.dumps({
            "op": "suspension_updated",
            "suspension": self.client
        }))

    def change_expiration(self, expiration: datetime):
        # Has to be separate to `edit` because the expiration can be None
        self.expires = expiration
        db.suspensions.update_one({"_id": self.id}, {"$set": {"expires": self.expires}})
        redis.publish("meower:cl", json.dumps({
            "op": "suspension_updated",
            "suspension": self.client
        }))

    def delete(self):
        db.appeal_messages.delete_many({"suspension_id": self.id})
        db.suspensions.delete_one({"_id": self.id})
        redis.publish("meower:cl", json.dumps({
            "op": "suspension_deleted",
            "user_id": self.user.id,
            "suspension_id": self.id
        }))

class AppealMessage:
    def __init__(
        self,
        _id: str,
        suspension_id: str,
        author_id: str,
        content: str,
        time: datetime
    ):
        self.id = _id
        self.suspension_id = suspension_id
        self.author = users.get_user(author_id)
        self.content = content
        self.time = time

    @property
    def public(self):
        return {
            "id": self.id,
            "suspension_id": self.suspension_id,
            "author": self.author.partial,
            "content": self.content,
            "time": self.time
        }
    
    def delete(self):
        db.appeal_messages.delete_one({"_id": self.id})

def create_suspension(
    user: users.User,
    moderator: users.User,
    suspended_features: int,
    reason: str,
    evaded_from: str = None,
    poisonous: bool = False,
    poison_last_ip: bool = False,
    poison_all_ips: bool = False,
    expires: datetime = None
):
    suspension = {
        "_id": uid.snowflake(),
        "user_id": user.id,
        "moderator_id": moderator.id,
        "evaded_from": evaded_from,
        "features": suspended_features,
        "reason": reason,
        "poisonous": poisonous,
        "started": uid.timestamp(),
        "expires": expires
    }

    db.suspensions.insert_one(suspension)
    suspension = Suspension(**suspension)
    redis.publish("meower:cl", json.dumps({
        "op": "suspension_updated",
        "suspension": suspension.client
    }))

    if poison_last_ip:
        last_netlog = networks.get_last_netlog(user)
        if last_netlog is not None:
            poison_network(netlog.network)
    elif poison_all_ips:
        for netlog in networks.get_all_netlogs(user):
            poison_network(netlog.network)
    
    return suspension

def get_suspension(suspension_id: str):
    suspension = db.suspensions.find_one({"_id": suspension_id})
    if suspension is None:
        return None
    else:
        return Suspension(**suspension)

def get_all_suspensions(user: users.User):
    return [Suspension(**suspension) for suspension in db.suspensions.find({"user_id": user.id})]

def get_active_suspensions(user: users.User):
    return [Suspension(**suspension) for suspension in db.suspensions.find({
        "user_id": user.id,
        "status": {"$ne": 4},
        "expires": {"$gt": uid.timestamp()}
    })]

def is_feature_suspended(user: users.User, feature: int):
    for suspension in get_active_suspensions(user):
        if not suspension.active:
            continue
        if bitfield.has(suspension.features, feature):
            return True
    return False

def poison_network(suspension: Suspension, network: networks.Network):
    for user in network.users:
        create_suspension(
            user,
            users.get_user("0"),
            suspension.features,
            f"Alternate account of @{suspension.user.username}",
            evaded_from=suspension.id,
            expires=suspension.expires
        )

def detect_ban_evasion(user: users.User, security_cookie: security_cookies.SecurityCookie, network: networks.Network):
    device_users = (user + [device_user for device_user in security_cookie.users])
    query = {
        "user_id": {"$in": [device_user.id for device_user in device_users]},
        "status": {"$ne": 4},
        "expires": {"$gt": uid.timestamp()}
    }
    for suspension in [Suspension(**suspension) for suspension in db.suspensions.find(query)]:
        if not suspension.active:
            continue
        if suspension.detect_alts:
            for possible_alt in (device_users + network.users):
                suspension.add_possible_alt(possible_alt)
        if suspension.poison_devices:
            for device_user in device_users:
                if device_user.id != suspension.user.id:
                    create_suspension(
                        device_user,
                        users.get_user("0"),
                        suspension.features,
                        f"Alternate account of @{suspension.user.username}",
                        evaded_from=suspension.id,
                        expires=suspension.expires
                    )

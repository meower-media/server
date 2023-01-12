"""
Idk about this, maybe should just be managed on the user object itself.
"""


from datetime import datetime
import json

from .stores import env
from .utils import uid, timestamp
from . import status
from .bitwise import flags, create_bitwise, check_flag, add_flag, remove_flag
from .database import db, redis

class Child:
    def __init__(
        self,
        _id: str,
        guardians: list = [],
        restrictions: str = 0,
        blocked_hours: dict = {},
        blocked_users: list = [],
        blocked_chats: list = []
    ):
        self._id = _id
        self.guardians = guardians
        self.restrictions = restrictions
        self.blocked_hours = blocked_hours
        self.blocked_users = blocked_users
        self.blocked_chats = blocked_chats

    @property
    def blocked(self):
        current_ts = timestamp()
        day = str(current_ts.weekday())
        hour = current_ts.hour
        return (check_flag(self.blocked_hours.get(day, 0), (1 << hour)) or check_flag(self.restrictions, flags.guardian.blocked))

    def link_guardian(self, email: str):
        if email not in self.guardians:
            self.guardians.append(email)
            db.users.update_one({"_id": self._id}, {"$push": {"guardian.guardians": self.guardians}})
            redis.publish("meower:cl", json.dumps({
                "op": "update_guardian",
                "user_id": self._id,
                "guardians": self.guardians
            }))

        raise status.ok

    def unlink_guardian(self, email: str):
        if email in self.guardians:
            self.guardians.remove(email)
            db.users.update_one({"_id": self._id}, {"$pull": {"guardian.guardians": self.guardians}})
            redis.publish("meower:cl", json.dumps({
                "op": "update_guardian",
                "user_id": self._id,
                "guardians": self.guardians
            }))

        raise status.ok

    def set_restrictions(self, restrictions: str):
        self.restrictions = restrictions
        db.users.update_one({"_id": self._id}, {"$set": {"guardian.restrictions": self.restrictions}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_guardian",
            "user_id": self._id,
            "restrictions": self.restrictions
        }))
        raise status.ok

    def set_blocked_hours(self, blocked_hours: dict):
        self.blocked_hours = blocked_hours
        db.users.update_one({"_id": self._id}, {"$set": {"guardian.blocked_hours": self.blocked_hours}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_guardian",
            "user_id": self._id,
            "blocked_hours": self.blocked_hours
        }))
        raise status.ok

    def block_user(self, user_id: str):
        if user_id not in self.blocked_users:
            self.blocked_users.append(user_id)
            db.users.update_one({"_id": self._id}, {"$push": {"guardian.blocked_users": self.blocked_users}})
            redis.publish("meower:cl", json.dumps({
                "op": "update_guardian",
                "user_id": self._id,
                "blocked_users": self.blocked_users
            }))

        raise status.ok

    def unblock_user(self, user_id: str):
        if user_id in self.blocked_users:
            self.blocked_users.remove(user_id)
            db.users.update_one({"_id": self._id}, {"$pull": {"guardian.blocked_users": self.blocked_users}})
            redis.publish("meower:cl", json.dumps({
                "op": "update_guardian",
                "user_id": self._id,
                "blocked_users": self.blocked_users
            }))

        raise status.ok

    def unlink_all_guardians(self):
        self.guardians = []
        db.users.update_one({"_id": self._id}, {"$set": {"guardian.guardians": self.guardians}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_guardian",
            "user_id": self._id,
            "guardians": self.guardians
        }))
        raise status.ok

    def remove_all_restrictions(self):
        self.restrictions = "0"
        self.blocked_hours = {}
        self.blocked_users = []
        self.blocked_chats = []
        db.users.update_one({"_id": self._id}, {"$set": {"guardian": {"guardians": self.guardians}}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_guardian",
            "user_id": self._id,
            "restrictions": self.restrictions,
            "blocked_users": self.blocked_users,
            "blocked_users": self.blocked_users,
            "blocked_chats": self.blocked_chats
        }))
        raise status.ok

def get_child(user_id: str):
    userdata = db.users.find_one({"_id": user_id}, projection={"_id": 1, "guardian": 1})
    guardian = userdata.get("guardian", {})
    guardian.update({"_id": userdata.get("_id")})

    if userdata is None:
        return None
    else:
        return Child(**guardian)

def get_all_children(email: str):
    children = []
    for userdata in db.users.find({"guardian.guardians": email}, projection={"_id": 1, "guardian": 1}):
        guardian = userdata.get("guardian", {})
        guardian.update({"_id": userdata["_id"]})
        children.append(Child(**guardian))
    return children

def unlink_all_children(email: str):
    for userdata in db.users.find({"guardian.guardians": email}, projection={"_id": 1, "guardian": 1}):
        guardian = userdata.get("guardian", {})
        guardian.update({"_id": userdata["_id"]})
        Child(**guardian).unlink_guardian(email)
    raise status.ok

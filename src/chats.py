"""
Painful thing to move across to the new entities folder, so haven't done so yet.
"""


from passlib.hash import bcrypt
from pyotp import TOTP
from secrets import token_urlsafe
from hashlib import sha256
from datetime import datetime
from threading import Thread
from copy import copy
import time
import json

from .stores import env
from .utils import uid, timestamp
from . import status
from .bitwise import flags, create_bitwise, check_flag, add_flag, remove_flag
from .database import db, redis
from .users import User, get_user

class Chat:
    def __init__(
        self,
        _id: str,
        nickname: str = None,
        icon: str = None,
        flags: int = 0,
        direct: bool = False,
        owner: str = None,
        members: list = [],
        permissions: dict = {},
        invite_code: str = None,
        last_message: str = None,
        created: datetime = None,
        delete_after: datetime = None
    ):
        self._id = _id
        self.nickname = nickname
        self.icon = icon
        self.flags = flags
        self.direct = direct
        self.owner = owner
        self.members = members
        self.permissions = permissions
        self.invite_code = invite_code
        self.last_message = last_message
        self.created = created
        self.delete_after = delete_after

    @property
    def public(self):
        return {
            "id": self._id,
            "nickname": self.nickname,
            "icon": self.icon,
            "flags": self.flags,
            "direct": self.direct,
            "owner": self.owner,
            "members": self.members,
            "permissions": self.permissions,
            "invite_code": self.invite_code,
            "last_message": self.last_message,
            "created": int(self.created.timestamp())
        }

    @property
    def partial(self):
        return {
            "id": self._id,
            "nickname": self.nickname,
            "icon": self.icon,
            "flags": self.flags,
            "direct": self.direct
        }

    def set_owner(self, user_id: str):
        if user_id not in self.members:
            raise status.notFound
        self.owner = user_id
        db.chats.update_one({"_id": self._id}, {"$set": {"owner": self.owner}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_chat",
            "chat_id": self._id,
            "owner": self.owner
        }))
        raise status.ok

    def add_member(self, user_id: str):
        if user_id in self.members:
            raise status.alreadyExists
        self.members.append(user_id)
        db.chats.update_one({"_id": self._id}, {"$push": {"members": user_id}})
        redis.publish("meower:cl", json.dumps({
            "op": "create_chat",
            "user_id": user_id,
            "chat": self.public
        }))
        redis.publish("meower:cl", json.dumps({
            "op": "update_chat",
            "chat_id": self._id,
            "members": self.members
        }))
        raise status.ok

    def remove_member(self, user_id: str):
        if user_id not in self.members:
            raise status.notFound
        self.members.remove(user_id)
        if user_id in self.permissions:
            del self.permissions[user_id]
        db.chats.update_one({"_id": self._id}, {"$pull": {"members": user_id}, "$set": {"permissions": self.permissions}})
        redis.publish("meower:cl", json.dumps({
            "op": "delete_chat",
            "chat_id": self._id,
            "user_id": user_id
        }))
        redis.publish("meower:cl", json.dumps({
            "op": "update_chat",
            "chat_id": self._id,
            "members": self.members
        }))
        raise status.ok

    def set_permission_level(self, user_id: str, level: int):
        if user_id not in self.members:
            raise status.notFound
        if (level < 0) or (level > 2):
            raise status.permissionLevelOutOfRange
        self.permissions.update(user_id, level)
        db.chats.update_one({"_id": self._id}, {"$set": {"permissions": self.permissions}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_chat",
            "chat_id": self._id,
            "permissions": self.permissions
        }))
        raise status.ok

    def refresh_invite_code(self):
        if check_flag(self.flags, flags.chat.vanityInviteCode):
            raise status.chatHasVanityInviteCode
        self.invite_code = token_urlsafe(6).replace("-", "A").replace("_", "a")
        db.chats.update_one({"_id": self._id}, {"$set": {"invite_code": self.invite_code}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_chat",
            "chat_id": self._id,
            "invite_code": self.invite_code
        }))
        raise status.ok

    def delete(self):
        if check_flag(self.flags, flags.chat.deleted):
            raise status.alreadyDeleted
        self.flags = add_flag(self.flags, flags.chat.deleted)
        self.delete_after = timestamp(epoch=(time.time() + 1209600))
        db.chats.update_one({"_id": self._id}, {"$set": {"flags": self.flags, "delete_after": self.delete_after}})
        redis.publish("meower:cl", json.dumps({
            "op": "delete_chat",
            "chat_id": self._id
        }))
        Thread(target=db.messages.update_many, args=({"chat": self._id}, {"delete_after": self.delete_after}))
        raise status.ok

    def undelete(self):
        if not check_flag(self.flags, flags.chat.deleted):
            raise status.notDeleted
        db.messages.update_many({"chat": self._id, "delete_after": self.delete_after}, {"delete_after": self.delete_after})
        self.flags = remove_flag(self.flags, flags.chat.deleted)
        self.delete_after = None
        db.chats.update_one({"_id": self._id}, {"$set": {"flags": self.flags, "delete_after": self.delete_after}})
        for user_id in self.members:
            redis.publish("meower:cl", json.dumps({
                "op": "create_chat",
                "user_id": user_id,
                "chat": self.public
            }))
        raise status.ok

    def create_message(self, author_id: str, content: str, system_alert: bool = False):
        message = {
            "_id": uid(),
            "chat": self._id,
            "author": author_id,
            "content": content,
            "time": timestamp()
        }
        if system_alert:
            message["flags"] = create_bitwise([flags.message.systemAlert])

        db.messages.insert_one(message)
        message = Message(**message)
        message_payload = message.public
        message_payload.update({"chat": self.partial, "author": get_user(author_id).partial})
        redis.publish("meower:cl", json.dumps({
            "op": "create_message",
            "message": message_payload
        }))

        self.last_message = message._id
        db.chats.update_one({"_id": self._id}, {"$set": {"last_message": self.last_message}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_chat",
            "chat_id": self._id,
            "last_message": self.last_message
        }))

        raise status.ok

    def get_messages(self, before: str = None, after: str = None, search: str = None, limit: int = 50):
        query = {"chat": self._id}
        if before is not None:
            query.update({"_id": {"$lt": before}})
        elif after is not None:
            query.update({"_id": {"$gt": after}})
        if search is not None:
            query.update({"content": {"$regex": search}})

        messages = [Message(**message).public for message in db.messages.find(query, sort=[("_id", -1)], limit=limit)]

        got_users = set()
        users = {}
        for message in messages:
            message["chat"] = self.partial
            if message["author"] not in got_users:
                users.update({message["author"]: get_user(message["author"]).partial})
            message["author"] = users[message["author"]]

        return messages

    def get_message_context(self, message_id: str):
        messages = []
        messages += self.get_messages(before=(str(int(message_id) - 1)), limit=51)
        messages += self.get_messages(after=message_id)
        return messages

class Message:
    def __init__(
        self,
        _id: str,
        chat: str = None,
        author: str = None,
        content: str = None,
        flags: int = 0,
        likes: list = [],
        time: datetime = None,
        deleted: bool = False,
        delete_after: datetime = None
    ):
        self._id = _id
        self.chat = chat
        self.author = author
        self.content = content
        self.flags = flags
        self.likes = likes
        self.time = time
        self.deleted = deleted
        self.delete_after = delete_after

    @property
    def public(self):
        return {
            "id": self._id,
            "chat": self.chat,
            "author": self.author,
            "content": self.content,
            "flags": self.flags,
            "likes": self.likes,
            "time": int(self.time.timestamp()),
            "deleted": self.deleted
        }

    def edit(self, content: str):
        self.content = content
        db.messages.update_one({"_id": self._id}, {"$set": {"content": self.content}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_message",
            "chat_id": self.chat,
            "message_id": self._id,
            "content": self.content
        }))
        raise status.ok

    def like(self, user_id: str):
        if user_id in self.likes:
            raise status.alreadyLiked
        self.likes.append(user_id)
        db.messages.update_one({"_id": self._id}, {"$push": {"likes": user_id}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_message",
            "chat_id": self.chat,
            "message_id": self._id,
            "likes": self.likes
        }))
        raise status.ok

    def unlike(self, user_id: str):
        if user_id not in self.likes:
            raise status.notLiked
        self.likes.remove(user_id)
        db.messages.update_one({"_id": self._id}, {"$pull": {"likes": user_id}})
        redis.publish("meower:cl", json.dumps({
            "op": "update_message",
            "chat_id": self.chat,
            "message_id": self._id,
            "likes": self.likes
        }))
        raise status.ok

    def delete(self):
        if self.deleted:
            raise status.alreadyDeleted
        self.deleted = True
        self.delete_after = timestamp(epoch=(time.time() + 1209600))
        db.messages.update_one({"_id": self._id}, {"$set": {"deleted": self.deleted, "delete_after": self.delete_after}})
        redis.publish("meower:cl", json.dumps({
            "op": "delete_message",
            "chat_id": self.chat,
            "message_id": self._id
        }))
        raise status.ok

def create_chat(nickname: str, owner_id: str):
    chat = {
        "_id": uid(),
        "nickname": nickname,
        "direct": False,
        "created": timestamp()
    }
    db.chats.insert_one(chat)
    chat = Chat(**chat)
    chat.refresh_invite_code()
    chat.add_member(owner_id)
    chat.set_owner(owner_id)
    return chat

def get_chat(chat_id: str):
    chat = db.chats.find_one({"_id": chat_id})

    if chat is None:
        raise status.notFound
    else:
        return Chat(**chat)

def get_chat_by_invite_code(invite_code: str):
    chat = db.chats.find_one({"invite_code": invite_code})

    if chat is None:
        raise status.notFound
    else:
        chat = Chat(**chat)

    if check_flag(chat.flags, flags.chat.inviteCodeDisabled) or check_flag(chat.flags, flags.chat.deleted):
        raise status.notFound
    
    return chat

def get_dm(user1: str, user2: str):
    chat = db.chats.find_one({"direct": True, "members": {"$all": [user1, user2]}})
    if chat is None:
        chat = {
            "_id": uid(),
            "direct": True,
            "members": [user1, user2],
            "created": timestamp()
        }
        db.chats.insert_one(chat)
        chat["owner"] = user1
        chat = Chat(**chat)
        redis.publish("meower:cl", json.dumps({
            "op": "create_chat",
            "user_id": user1,
            "chat": chat.public
        }))
    chat["owner"] = user1
    chat = Chat(**chat)
    return chat

def get_message(message_id: str):
    message = db.messages.find_one({"_id": message_id})
    if message is None:
        raise status.notFound
    return Message(**message)

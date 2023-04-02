from secrets import token_urlsafe
import ujson
import time

from src.common.entities import users, posts
from src.common.util import uid, errors, events
from src.common.database import db, redis, count_pages


LIVECHAT = {
    "_id": "livechat",
    "nickname": None,
    "owner": None,
    "members": [],
    "invite_code": None,
    "created": None
}


class Chat:
    def __init__(
        self,
        _id: str,
        nickname: str,
        owner: str,
        members: list,
        invite_code: str,
        created: int
    ):
        self.id = _id
        self.nickname = nickname
        self.owner = owner
        self.members = members
        self.invite_code = invite_code
        self.created = created

    @property
    def public(self):
        return {
            "_id": self.id,
            "nickname": self.nickname,
            "owner": self.owner,
            "members": self.members,
            "invite_code": self.invite_code,
            "created": self.created
        }

    def change_nickname(self, new_nickname: str) -> bool:
        # Make sure the chat isn't livechat
        if self.id == "livechat":
            raise errors.MissingPermissions

        # Change nickname
        self.nickname = new_nickname
        db.chats.update_one({"_id": self.id}, {"$set": {"nickname": self.nickname}})

        # Delete cache
        redis.delete(f"chat:{self.id}")

        # Send chat update event
        self.send_chat_update_event()

    def change_owner(self, username: str, actor: str = None) -> bool:
        # Make sure the chat isn't livechat
        if self.id == "livechat":
            raise errors.MissingPermissions

        # Change owner
        if username not in self.members:
            raise errors.ChatMemberNotFound
        self.owner = username
        db.chats.update_one({"_id": self.id}, {"$set": {"owner": self.owner}})

        # Delete cache
        redis.delete(f"chat:{self.id}")

        # Send chat update event
        self.send_chat_update_event()

        # Send message in chat
        if actor:
            posts.create_post(self.id, "Server", f"@{actor} transferred ownership of the group chat to @{username}.")

    def add_member(self, username: str, actor: str):
        # Make sure the chat isn't livechat
        if self.id == "livechat":
            raise errors.MissingPermissions

        # Check if user is accepting chat invites
        user = users.get_user(username)
        if (username != actor) and (not user.accepting_invites):
            raise errors.MissingPermissions

        # Add member
        if username in self.members:
            raise errors.AlreadyExists
        self.members.append(username)
        db.chats.update_one({"_id": self.id}, {"$addToSet": {"members": username}})

        # Delete cache
        redis.delete(f"chat:{self.id}")

        # Send chat update event
        self.send_chat_update_event()

        # Send message in chat
        if actor == username:
            posts.create_post(self.id, "Server", f"@{username} joined the group chat via an invite code.")
        else:
            posts.create_post(self.id, "Server", f"@{actor} added @{username} to the group chat.")
    
    def remove_member(self, username: str, actor: str):
        # Make sure the chat isn't livechat
        if self.id == "livechat":
            raise errors.MissingPermissions

        # Remove member
        if username not in self.members:
            raise errors.NotFound
        self.members.remove(username)

        if len(self.members) == 0:  # Delete chat if no members are left
            self.delete()
            return
        else:
            if self.owner == username:  # Transfer ownership if user was owner
                self.owner = self.members[0]
            db.chats.update_one({"_id": self.id}, {"$set": {"owner": self.owner}, "$pull": {"members": username}})

        # Delete cache
        redis.delete(f"chat:{self.id}")

        # Send chat update event
        self.send_chat_update_event()

        # Send message in chat
        if actor == username:
            posts.create_post(self.id, "Server", f"@{username} left the group chat.")
        else:
            posts.create_post(self.id, "Server", f"@{actor} removed @{username} from the group chat.")

    def set_chat_state(self, username: str, state: int):
        events.send_event("update_chat_state", {
            "chatid": self.id,
            "u": username,
            "state": state
        })

    def reset_invite_code(self):
        # Make sure the chat isn't livechat
        if self.id == "livechat":
            raise errors.MissingPermissions

        # Update chat invite code
        self.invite_code = token_urlsafe(5)
        db.chats.update_one({"_id": self.id}, {"$set": {"invite_code": self.invite_code}})

        # Send chat update event
        self.send_chat_update_event()

    def send_chat_update_event(self):
        events.send_event("update_chat", self.public)

    def delete(self):
        # Make sure the chat isn't livechat
        if self.id == "livechat":
            raise errors.MissingPermissions
        
        # Delete properties
        self.nickname = None
        self.owner = None
        self.members = []
        self.invite_code = None
        self.created = None

        # Delete chat from database
        db.chats.delete_one({"_id": self.id})

        # Delete cache
        redis.delete(f"chat:{self.id}")

        # Send chat update event
        self.send_chat_update_event()


def create_chat(nickname: str, owner: str) -> Chat:
    # Create chat ID
    chat_id = uid.uuid()

    # Create chat data
    chat_data = {
        "_id": chat_id,
        "nickname": nickname,
        "owner": owner,
        "members": [owner],
        "invite_code": token_urlsafe(5),
        "created": int(time.time())
    }

    # Insert chat into database
    db.chats.insert_one(chat_data)

    # Add chat to cache
    redis.set(f"chat:{chat_id}", ujson.dumps(chat_data), ex=120)

    # Get chat object
    chat = Chat(**chat_data)

    # Send chat update event
    chat.send_chat_update_event()

    # Return chat object
    return chat


def get_chat(chat_id: str) -> Chat:
    # Get livechat
    if chat_id == "livechat":
        return Chat(**LIVECHAT)

    # Get chat from cache
    chat_data = redis.get(f"chat:{chat_id}")
    if chat_data:
        chat_data = ujson.loads(chat_data)

    # Get chat from database and add to cache
    if not chat_data:
        chat_data = db.chats.find_one({"_id": chat_id})
        if chat_data:
            redis.set(f"chat:{chat_id}", ujson.dumps(chat_data), ex=120)

    # Return chat object
    if chat_data:
        return Chat(**chat_data)
    else:
        raise errors.NotFound


def get_chat_by_invite_code(invite_code: str) -> Chat:
    # Get chat from database and add to cache
    chat_data = db.chats.find_one({"invite_code": invite_code})
    if chat_data:
        chat_id = chat_data["_id"]
        redis.set(f"chat:{chat_id}", ujson.dumps(chat_data), ex=120)
    
    # Return chat object
    if chat_data:
        return Chat(**chat_data)
    else:
        raise errors.NotFound


def get_users_chats(username: str, page: int = 1) -> list[Chat]:
    query = {"members": {"$all": [username]}}
    return count_pages("chats", query), [Chat(**chat) for chat in db.chats.find(query,
                                                   sort=[("created", -1)],
                                                   skip=(((page-1)*25) if page else None),
                                                   limit=(25 if page else None))]


def get_all_chat_ids(username: str) -> list[str]:
    return [chat["_id"] for chat in db.chats.find({"members": {"$all": [username]}}, projection={"_id": 1})]

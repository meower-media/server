from datetime import datetime
import time

from src.util import status, uid, events, bitfield, flags
from src.entities import users, chats
from src.database import db

class Message:
    def __init__(
        self,
        _id: str,
        chat_id: str,
        author_id: str = None,
        masquerade: dict = None,
        reply_to: str = None,
        flags: int = 0,
        content: str = None,
        likes: list = [],
        time: datetime = None,
        delete_after: datetime = None,
        deleted_at: datetime = None
    ):
        self.id = _id
        self.chat_id = chat_id
        self.author = users.get_user(author_id)
        self.masquerade = masquerade
        self.reply_to = reply_to
        self.flags = flags
        self.content = content
        self.likes = likes
        self.time = time
        self.delete_after = delete_after
        self.deleted_at = deleted_at

    @property
    def public(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "author": self.author.partial,
            "masquerade": self.masquerade,
            "reply_to": self.reply_to,
            "flags": self.flags,
            "content": self.content,
            "filtered_content": self.content,  # Need to find a suitable filter, may end up being client-side
            "likes": self.likes,
            "time": int(self.time.timestamp()),
            "delete_after": (int(self.delete_after.timestamp()) if self.delete_after else None)
        }

    def liked(self, user: any):
        return (user.id in self.likes)

    def like(self, user: any):
        if self.liked(user):
            return
        
        self.likes.append(user.id)
        db.chat_messages.update_one({"_id": self.id}, {"$addToSet": {"likes": user.id}})
        events.emit_event("message_updated", self.chat_id, {
            "id": self.id,
            "chat_id": self.chat_id,
            "likes": self.likes
        })

    def unlike(self, user: any):
        if not self.liked(user):
            return
        
        self.likes.remove(user.id)
        db.chat_messages.update_one({"_id": self.id}, {"$pull": {"likes": user.id}})
        events.emit_event("message_updated", self.chat_id, {
            "id": self.id,
            "chat_id": self.chat_id,
            "likes": self.likes
        })

    def edit(self, content: str):
        db.chat_message_revisions.insert_one({
            "_id": uid.snowflake(),
            "message_id": self.id,
            "old_content": self.content,
            "new_content": content,
            "time": uid.timestamp()
        })

        self.flags = bitfield.add(self.flags, flags.messages.edited)
        self.content = content
        db.chat_messages.update_one({"_id": self.id}, {"$set": {
            "flags": self.flags,
            "content": self.content
        }})
        events.emit_event("message_updated", self.chat_id, {
            "id": self.id,
            "chat_id": self.chat_id,
            "flags": self.flags,
            "content": self.content
        })

    def delete(self):
        self.deleted_at = uid.timestamp()
        db.chat_messages.update_one({"_id": self.id}, {"$set": {"deleted_at": self.deleted_at}})
        events.emit_event("message_deleted", self.chat_id, {
            "id": self.id,
            "chat_id": self.chat_id
        })

def create_message(chat: chats.Chat, author: any, content: str, reply_to: str = None, masquerade: dict = None, bridged: bool = False):
    # Check whether a DM can be sent
    if chat.direct:
        for member in chat.members:
            if member.id != author.id:
                if member.is_blocked(author):
                    raise status.missingPermissions

    # Create message data
    message = {
        "_id": uid.snowflake(),
        "chat_id": chat.id,
        "author_id": author.id,
        "masquerade": masquerade,
        "reply_to": reply_to,
        "flags": (bitfield.create([flags.messages.bridged]) if bridged else 0),
        "content": content,
        "time": uid.timestamp()
    }

    # Insert message into database and convert into message object
    db.chat_messages.insert_one(message)
    message = Message(**message)

    # Announce message creation
    events.emit_event("message_created", message.chat_id, message.public)

    # Return message object
    return message

def get_message(message_id: str, error_on_deleted: bool = True):
    # Get message from database
    message = db.chat_messages.find_one({"_id": message_id})

    # Return message object
    if message and ((not error_on_deleted) or (not message.get("deleted_at"))):
        return Message(**message)
    else:
        raise status.resourceNotFound

def get_latest_messages(chat: chats.Chat, before: str = None, after: str = None, limit: int = 50):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all messages
    return [Message(**message) for message in db.chat_messages.find({"chat_id": chat.id, "deleted_at": None, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

def get_message_context(chat: chats.Chat, message_id: str):
    return (get_latest_messages(chat, before=str(int(message_id)+1), limit=51) + get_latest_messages(chat, after=message_id))

def search_messages(chat: chats.Chat, query: str, before: str = None, after: str = None, limit: int = 50):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all messages
    return [Message(**message) for message in db.chat_messages.find({"chat_id": chat.id, "deleted_at": None, "$text": {"$search": query}, "_id": id_range}, sort=[("_id", -1)], limit=limit)]
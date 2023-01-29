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
        reply_to: str = None,
        content: str = None,
        flags: str = 0,
        likes: list = [],
        time: datetime = None,
        deleted: bool = False,
        delete_after: datetime = None
    ):
        self.id = _id
        self.chat_id = chat_id
        self.author = users.get_user(author_id)
        self.reply_to = reply_to
        self.content = content
        self.flags = flags
        self.likes = likes
        self.time = time
        self.deleted = deleted
        self.delete_after = delete_after

    @property
    def public(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "author": self.author.partial,
            "reply_to": self.reply_to,
            "content": self.content,
            "filtered_content": self.content,  # Need to find a suitable filter, may end up being client-side
            "flags": self.flags,
            "likes": self.likes,
            "time": int(self.time.timestamp()),
            "delete_after": (int(self.delete_after.timestamp()) if (self.delete_after is not None) else None)
        }

    def liked(self, user: users.User):
        return (user.id in self.likes)

    def like(self, user: users.User):
        if self.liked(user):
            raise status.alreadyLiked
        
        self.likes.append(user.id)
        db.chat_messages.update_one({"_id": self.id}, {"$addToSet": {"likes": user.id}})
        events.emit_event("message_updated", self.chat_id, {
            "id": self.id,
            "chat_id": self.chat_id,
            "likes": self.likes
        })

    def unlike(self, user: users.User):
        if not self.liked(user):
            raise status.notLiked
        
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

        self.flags = bitfield.add(self.flags, flags.message.edited)
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
        if self.deleted:
            db.chat_message_revisions.delete_many({"message_id": self.id})
            db.chat_messages.delete_one({"_id": self.id})
        else:
            self.deleted = True
            self.delete_after = uid.timestamp(epoch=int(time.time() + 1209600))
            db.chat_messages.update_one({"_id": self.id}, {"$set": {"deleted": self.deleted, "delete_after": self.delete_after}})
            events.emit_event("message_deleted", self.chat_id, {
                "id": self.id,
                "chat_id": self.chat_id
            })

def create_message(chat: chats.Chat, author: users.User, content: str, reply_to: str = None):
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
        "reply_to": reply_to,
        "content": content,
        "time": uid.timestamp(),
        "deleted": False
    }

    # Insert message into database and convert into message object
    db.chat_messages.insert_one(message)
    message = Message(**message)

    # Announce message creation
    events.emit_event("message_created", message.chat_id, message.public)

    # Return message object
    return message

def get_message(message_id: str, error_on_deleted: bool = True):
    # Get message from database and check whether it's not found or deleted
    message = db.chat_messages.find_one({"_id": message_id})
    if message is None or (error_on_deleted and message.get("deleted")):
        raise status.notFound

    # Return message object
    return Message(**message)

def get_latest_messages(chat: chats.Chat, before: str = None, after: str = None, limit: int = 50):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all messages
    return [Message(**message) for message in db.chat_messages.find({"chat_id": chat.id, "deleted": False, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

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
    return [Message(**message) for message in db.chat_messages.find({"chat_id": chat.id, "deleted": False, "$text": {"$search": query}, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

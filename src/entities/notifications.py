from datetime import datetime
from threading import Thread

from src.util import status, uid, events
from src.entities import users
from src.database import db

class Notification:
    def __init__(
        self,
        _id: str,
        recipient_id: str = None,
        type: int = None,
        content: str = None,
        link: str = None,
        read: bool = False,
        time: datetime = None
    ):
        self.id = _id
        self.recipient = users.get_user(recipient_id)
        self.type = type
        self.content = content
        self.link = link
        self.read = read
        self.time = time

    @property
    def client(self):
        return {
            "id": self.id,
            "recipient": self.recipient.partial,
            "type": self.type,
            "content": self.content,
            "link": self.link,
            "read": self.read,
            "time": int(self.time.timestamp())
        }

    def edit(self, content: str = None, link: str = None, read: bool = None):
        if content is not None:
            self.content = content
        if link is not None:
            self.link = link
        if read is not None:
            self.read = read
        db.notifications.update_one({"_id": self.id}, {"$set": {
            "content": self.content,
            "link": self.link,
            "read": self.read
        }})
        
        if not self.read:
            Thread(target=emit_user_notification_unread_count, args=(self.recipient)).start()

    def delete(self):
        db.chat_messages.delete_one({"_id": self.id})

        if not self.read:
            Thread(target=emit_user_notification_unread_count, args=(self.recipient)).start()

def create_notification(recipient: users.User, type: int, content: str, link: str = None):
    # Create notification data
    notification = {
        "_id": uid.snowflake(),
        "recipient_id": recipient.id,
        "type": type,
        "content": content,
        "link": link,
        "read": False,
        "time": uid.timestamp()
    }

    # Insert notification into database and convert into Notification object
    db.notifications.insert_one(notification)
    notification = Notification(**notification)

    # Announce new notification count
    Thread(target=emit_user_notification_unread_count, args=(recipient)).start()

    # Return notification object
    return notification

def get_notification(notification_id: str):
    # Get notification from database
    notification = db.notifications.find_one({"_id": notification_id})
    if notification is None:
        raise status.notFound # placeholder

    # Return notification object
    return Notification(**notification)

def get_user_notifications(user: users.User, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all notifications
    return [Notification(**notification) for notification in db.notifications.find({"recipient_id": user.id, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

def get_user_notification_unread_count(user: users.User):
    return db.notifications.count_documents({"recipient_id": user.id, "read": False})

def emit_user_notification_unread_count(user: users.User):
    unread_notifications = get_user_notification_unread_count(user)
    events.emit_event(f"notification_unread_count_updated", {
        "unread": unread_notifications
    })

def clear_unread_user_notifications(user: users.User):
    db.notifications.update_many({"recipient_id": user.id, "read": False}, {"$set": {"read": True}})

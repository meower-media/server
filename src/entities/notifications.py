from datetime import datetime
from threading import Thread

from src.util import status, uid, events
from src.entities import users, posts, comments
from src.database import db

class Notification:
    def __init__(
        self,
        _id: str,
        recipient_id: str = None,
        type: int = None,
        data: dict = {},
        read: bool = False,
        time: datetime = None
    ):
        self.id = _id
        self.recipient = users.get_user(recipient_id)
        self.type = type
        self.data = data
        self.read = read
        self.time = time

    @property
    def client(self):
        data = {
            "id": self.id,
            "recipient": self.recipient.partial,
            "type": self.type,
            "read": self.read,
            "time": int(self.time.timestamp())
        }

        if self.type == 0:
            data["content"] = self.data.get("content")
        if self.type == 1:
            try:
                data["user"] = users.get_user(self.data["user_id"]).partial
            except:
                data["user"] = None
        elif (self.type == 2) or (self.type == 3):
            try:
                data["post"] = posts.get_post(self.data["post_id"]).public
                data["milestone"] = self.data["milestone"]
            except:
                data["post"] = None
                data["milestone"] = None
        elif (self.type == 4) or (self.type == 6):
            try:
                data["comment"] = comments.get_comment(self.data["comment_id"]).public
            except:
                data["comment"] = None
        elif self.type == 5:
            try:
                data["comment"] = comments.get_comment(self.data["comment_id"]).public
                data["milestone"] = self.data["milestone"]
            except:
                data["comment"] = None
                data["milestone"] = None

        return data

    def mark(self, read_status: bool):
        self.read = read_status
        db.notifications.update_one({"_id": self.id}, {"$set": {"read": self.read}})
        Thread(target=emit_user_notification_unread_count, args=(self.recipient,)).start()

    def delete(self):
        db.notifications.delete_one({"_id": self.id})
        Thread(target=emit_user_notification_unread_count, args=(self.recipient,)).start()

def create_notification(recipient: any, type: int, data: dict):
    # Create notification data
    notification = {
        "_id": uid.snowflake(),
        "recipient_id": recipient.id,
        "type": type,
        "data": data,
        "read": False,
        "time": uid.timestamp()
    }

    # Insert notification into database and convert into Notification object
    db.notifications.insert_one(notification)
    notification = Notification(**notification)

    # Announce new notification count
    Thread(target=emit_user_notification_unread_count, args=(recipient,)).start()

    # Return notification object
    return notification

def get_notification(notification_id: str):
    # Get notification from database
    notification = db.notifications.find_one({"_id": notification_id})

    # Return notification object
    if notification:
        return Notification(**notification)
    else:
        raise status.resourceNotFound

def get_user_notifications(user: any, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all notifications
    return [Notification(**notification) for notification in db.notifications.find({"recipient_id": user.id, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

def get_user_notification_unread_count(user: any):
    return db.notifications.count_documents({"recipient_id": user.id, "read": False})

def emit_user_notification_unread_count(user: any):
    unread_notifications = get_user_notification_unread_count(user)
    events.emit_event("notification_count_updated", user.id, {
        "unread": unread_notifications
    })

def clear_unread_user_notifications(user: any):
    db.notifications.update_many({"recipient_id": user.id, "read": False}, {"$set": {"read": True}})
    Thread(target=emit_user_notification_unread_count, args=(user,)).start()

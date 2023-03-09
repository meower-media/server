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

        if self.type == 0:  # standard content
            data["content"] = self.data.get("content")
        elif self.type == 1:  # user follow
            try:
                data["user"] = users.get_user(self.data["user_id"]).partial
            except:
                data["user"] = None
        elif self.type == 2:  # post mention
            try:
                data["post"] = posts.get_post(self.data["post_id"]).public
            except:
                data["post"] = None
        elif (self.type == 3) or (self.type == 4) or (self.type == 5):  # comment mention, post comment, or comment reply
            try:
                data["comment"] = comments.get_comment(self.data["comment_id"]).public
            except:
                data["comment"] = None
        elif (self.type == 6) or (self.type == 7):  # post like/meow milestone
            try:
                data["post"] = posts.get_post(self.data["post_id"]).public
                data["milestone"] = self.data["milestone"]
            except:
                data["post"] = None
                data["milestone"] = None
        elif self.type == 8:  # comment like milestone
            try:
                data["comment"] = comments.get_comment(self.data["comment_id"]).public
                data["milestone"] = self.data["milestone"]
            except:
                data["comment"] = None
                data["milestone"] = None

        return data
    
    @property
    def legacy_client(self):
        try:
            if self.type == 0:  # standard content
                content = self.data["content"]
            elif self.type == 1:  # user follow
                user = users.get_user(self.data["user_id"])
                content = f"@{user.username} started following you!"
            elif self.type == 2:  # post mention
                post = posts.get_post(self.data["post_id"])
                content = f"@{post.author.username} mentioned you in a post! Post: '{(post.filtered_content if post.filtered_content else post.content)}'"
            elif self.type == 3: # comment mention
                comment = comments.get_comment(self.data["comment_id"])
                content = f"@{post.author.username} mentioned you in a comment! Comment: '{(comment.filtered_content if comment.filtered_content else comment.content)}'"
            elif self.type == 4:  # post comment
                comment = comments.get_comment(self.data["comment_id"])
                content = f"@{post.author.username} made a comment on your post! Comment: '{(comment.filtered_content if comment.filtered_content else comment.content)}'"
            elif self.type == 5:  # comment reply
                comment = comments.get_comment(self.data["comment_id"])
                content = f"@{post.author.username} replied to your comment! Comment: '{(comment.filtered_content if comment.filtered_content else comment.content)}'"
            elif self.type == 6:  # post like milestone
                post = posts.get_post(self.data["post_id"])
                milestone = self.data["milestone"]
                content = f"You reached {str(milestone)} likes on your post! Post: '{(post.filtered_content if post.filtered_content else post.content)}'"
            elif self.type == 7:  # post meow milestone
                post = posts.get_post(self.data["post_id"])
                milestone = self.data["milestone"]
                content = f"You reached {str(milestone)} meows on your post! Post: '{(post.filtered_content if post.filtered_content else post.content)}'"
            elif self.type == 8:  # comment like milestone
                comment = comments.get_comment(self.data["comment_id"])
                milestone = self.data["milestone"]
                content = f"You reached {str(milestone)} likes on your comment! Comment: '{(comment.filtered_content if comment.filtered_content else comment.content)}'"
        except:
            content = "Unable to parse notification!"

        return {
            "_id": self.id,
            "type": 2,
            "post_origin": "inbox",
            "u": self.recipient.username,
            "t": uid.timestamp(epoch=int(self.time.timestamp()), jsonify=True),
            "p": content,
            "post_id": self.id,
            "isDeleted": False
        }

    def mark(self, read_status: bool):
        self.read = read_status
        db.notifications.update_one({"_id": self.id}, {"$set": {"read": self.read}})
        Thread(target=emit_user_notification_unread_count, args=(self.recipient.id,)).start()

    def delete(self):
        db.notifications.delete_one({"_id": self.id})
        Thread(target=emit_user_notification_unread_count, args=(self.recipient.id,)).start()

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
    Thread(target=emit_user_notification_unread_count, args=(recipient.id,)).start()

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

def get_user_notifications(user_id: str, before: str = None, after: str = None, skip: int = 0, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all notifications
    return [Notification(**notification) for notification in db.notifications.find({"recipient_id": user_id, "_id": id_range}, sort=[("time", -1)], skip=skip, limit=limit)]

def get_user_notification_unread_count(user_id: str):
    return db.notifications.count_documents({"recipient_id": user_id, "read": False})

def emit_user_notification_unread_count(user_id: str):
    unread_notifications = get_user_notification_unread_count(user_id)
    events.emit_event("notification_count_updated", user_id, {
        "unread": unread_notifications
    })

def clear_unread_user_notifications(user_id: str):
    db.notifications.update_many({"recipient_id": user_id, "read": False}, {"$set": {"read": True}})
    Thread(target=emit_user_notification_unread_count, args=(user_id,)).start()

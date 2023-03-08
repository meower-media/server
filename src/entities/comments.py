from datetime import datetime
from copy import copy
from threading import Thread
import re

from src.util import status, uid, regex, events, filter, bitfield, flags
from src.entities import users, posts, notifications
from src.database import db

class Comment:
    def __init__(
        self,
        _id: str,
        post_id: str,
        parent_id: str = None,
        author_id: str = None,
        masquerade: dict = None,
        flags: int = 0,
        likes: int = 0,
        top_likes: int = 0,
        content: str = None,
        filtered_content: str = None,
        time: datetime = None,
        delete_after: datetime = None,
        deleted_at: datetime = None
    ):
        self.id = _id
        self.post_id = post_id
        self.parent_id = parent_id
        self.author = users.get_user(author_id)
        self.masquerade = masquerade
        self.flags = flags
        self.likes = likes
        self.top_likes = top_likes
        self.content = content
        self.filtered_content = filtered_content
        self.time = time
        self.delete_after = delete_after
        self.deleted_at = deleted_at

    @property
    def public(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "parent_id": self.parent_id,
            "author": self.author.partial,
            "masquerade": self.masquerade,
            "public_flags": self.public_flags,
            "likes": self.likes,
            "content": self.content,
            "filtered_content": self.filtered_content,
            "time": int(self.time.timestamp()),
            "delete_after": (int(self.delete_after.timestamp()) if self.delete_after else None)
        }

    @property
    def admin(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "parent_id": self.parent_id,
            "author": self.author.partial,
            "masquerade": self.masquerade,
            "flags": self.flags,
            "public_flags": self.public_flags,
            "likes": self.likes,
            "top_likes": self.top_likes,
            "content": self.content,
            "filtered_content": self.filtered_content,
            "time": int(self.time.timestamp()),
            "delete_after": (int(self.delete_after.timestamp()) if self.delete_after else None),
            "deleted_at": (int(self.deleted_at.timestamp()) if self.deleted_at else None)
        }

    @property
    def public_flags(self):
        pub_flags = copy(self.flags)
        for flag in []:
            pub_flags = bitfield.remove(pub_flags, flag)
        return pub_flags

    @property
    def public_revisions(self):
        return self.get_revisions(include_private=False)

    @property
    def admin_revisions(self):
        return self.get_revisions(include_private=True)

    def update_stats(self):
        def run():
            self.likes = db.comment_likes.count_documents({"post_id": self.id})
            if self.likes > self.top_likes:
                for milestone in [5, 10, 25, 50, 100, 1000]:
                    if (self.likes >= milestone) and (self.top_likes < milestone):
                        if self.author.config["notification_settings"]["comment_likes"]:
                            notifications.create_notification(self.author, 8, {
                                "comment_id": self.id,
                                "milestone": milestone
                            })
                
                self.top_likes = self.likes

            db.post_comments.update_one({"_id": self.id}, {"$set": {
                "likes": self.likes,
                "top_likes": self.top_likes
            }})
            events.emit_event("comment_updated", self.post_id, {
                "id": self.id,
                "likes": self.likes
            })
        Thread(target=run).start()

    def liked(self, user: any):
        return (db.comment_likes.count_documents({"comment_id": self.id, "user_id": user.id}) > 0)

    def like(self, user: any):
        if self.liked(user):
            return
        
        db.comment_likes.insert_one({
            "_id": uid.snowflake(),
            "comment_id": self.id,
            "user_id": user.id,
            "time": uid.timestamp()
        })
        events.emit_event("comment_status_updated", user.id, {
            "id": self.id,
            "liked": True
        })
        self.update_stats()

    def unlike(self, user: any):
        if not self.liked(user):
            return

        db.comment_likes.delete_one({
            "comment_id": self.id,
            "user_id": user.id
        })
        events.emit_event("comment_status_updated", user.id, {
            "id": self.id,
            "liked": False
        })
        self.update_stats()

    def edit(self, editor: any, content: str):
        if bitfield.has(self.flags, flags.posts.protected):
            raise status.missingPermissions
        elif content == self.content:
            return
        
        db.comment_revisions.insert_one({
            "_id": uid.snowflake(),
            "comment_id": self.id,
            "old_content": self.content,
            "new_content": content,
            "editor_id": editor.id,
            "time": uid.timestamp()
        })

        self.flags = bitfield.add(self.flags, flags.comments.edited)
        self.content = content
        db.post_comments.update_one({"_id": self.id}, {"$set": {
            "flags": self.flags,
            "content": self.content
        }})
        events.emit_event("comment_updated", self.post_id, {
            "id": self.id,
            "flags": self.public_flags,
            "content": self.content
        })

    def get_revisions(self, include_private: bool = False):
        query = {"post_id": self.id}
        if not include_private:
            query["public"] = True
        
        revisions = []
        for revision in db.comment_revisions.find(query):
            revision["id"] = revision["_id"]
            revision["editor"] = users.get_user(revision["editor_id"]).partial
            del revision["_id"]
            del revision["editor_id"]
        return revisions

    def change_revision_privacy(self, revision_id: str, public: bool):
        db.comment_revisions.update_one({"_id": revision_id}, {"$set": {"public": public}})
    
    def delete_revision(self, revision_id: str):
        db.comment_revisions.delete_one({"_id": revision_id})

    def delete(self):
        self.deleted_at = uid.timestamp()
        db.post_comments.update_one({"_id": self.id}, {"$set": {"deleted_at": self.deleted_at}})
        events.emit_event("comment_deleted", self.post_id, {
            "id": self.id
        })

def create_comment(post: posts.Post, author: any, content: str, parent: Comment = None, masquerade: dict = None, bridged: bool = False):
    # Create comment data
    comment = {
        "_id": uid.snowflake(),
        "post_id": post.id,
        "parent_id": (parent.id if parent else None),
        "author_id": author.id,
        "masquerade": masquerade,
        "flags": (bitfield.create([flags.comments.bridged]) if bridged else 0),
        "content": content,
        "filtered_content": None,
        "time": uid.timestamp(),
        "deleted_at": None
    }

    # Filter profanity
    filtered_content = filter.censor(content)
    if filtered_content != content:
        comment["filtered_content"] = filtered_content

    # Insert comment into database and convert into Comment object
    db.post_comments.insert_one(comment)
    comment = Comment(**comment)

    # Announce comment creation
    events.emit_event("comment_created", post.id, comment.public)

    # Send notifications
    if post.author.id != comment.author.id:
        if post.author.config["notification_settings"]["comments"]:
            notifications.create_notification(post.author, 4, {
                "comment_id": comment.id
            })
    if parent and (parent.author.id != comment.author.id):
        if post.author.config["notification_settings"]["comment_replies"]:
            notifications.create_notification(parent.author, 5, {
                "comment_id": comment.id
            })

    # Notify mentioned users
    notify_users = set()
    for username, notify in [regex.extract_mention(mention) for mention in re.findall(regex.USER_MENTION, content)]:
        if username == comment.author.username:
            continue
        if username == post.author.username:
            continue
        if parent and (username == parent.author.username):
            continue
        if notify:
            notify_users.add(username)
    for username in notify_users:
        try:
            user = users.get_user(users.get_id_from_username(username), return_deleted=False)
            if user.config["notification_settings"]["mentions"]:
                notifications.create_notification(user, 3, {
                    "comment_id": comment.id
                })
        except:
            pass

    # Return comment object
    return comment

def get_comment(comment_id: str, error_on_deleted: bool = True):
    # Get comment from database
    comment = db.post_comments.find_one({"_id": comment_id})

    # Return comment object
    if comment and ((not error_on_deleted) or (not comment.get("deleted_at"))):
        return Comment(**comment)
    else:
        raise status.resourceNotFound

def get_post_comments(post: posts.Post, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return comments
    return [Comment(**comment) for comment in db.post_comments.find({"post_id": post.id, "parent_id": None, "deleted_at": None, "_id": id_range}, sort=[("time", -1)], limit=limit)]

def get_comment_replies(comment: Comment, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return comments
    return [Comment(**comment) for comment in db.post_comments.find({"post_id": comment.post_id, "parent_id": comment.id, "deleted_at": None, "_id": id_range}, sort=[("time", -1)], limit=limit)]

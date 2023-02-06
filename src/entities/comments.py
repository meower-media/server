from datetime import datetime
from copy import copy
from threading import Thread
import time

from src.util import status, uid, events, filter, bitfield, flags
from src.entities import users, posts
from src.database import db

class Comment:
    def __init__(
        self,
        _id: str,
        post_id: str,
        parent_id: str = None,
        author_id: str = None,
        content: str = None,
        filtered_content: str = None,
        flags: str = 0,
        stats: dict = {
            "likes": 0,
            "replies": 0
        },
        time: datetime = None,
        delete_after: datetime = None,
        deleted_at: datetime = None
    ):
        self.id = _id
        self.post_id = post_id
        self.parent_id = parent_id
        self.author = users.get_user(author_id)
        self.content = content
        self.filtered_content = filtered_content
        self.flags = flags
        self.stats = stats
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
            "content": self.content,
            "filtered_content": self.filtered_content,
            "public_flags": self.public_flags,
            "stats": self.stats,
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
            "content": self.content,
            "filtered_content": self.filtered_content,
            "flags": self.flags,
            "public_flags": self.public_flags,
            "stats": self.stats,
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
            self.stats = {
                "likes": db.comment_likes.count_documents({"post_id": self.id}),
                "replies": db.post_comments.count_documents({"post_id": self.post_id, "parent_id": self.id, "deleted_at": None})
            }
            db.post_comments.update_one({"_id": self.id}, {"$set": {"stats": self.stats}})
            events.emit_event("comment_updated", self.post_id, {
                "id": self.id,
                "stats": self.stats
            })
        Thread(target=run).start()

    def liked(self, user: users.User):
        return (db.comment_likes.count_documents({"comment_id": self.id, "user_id": user.id}) > 0)

    def like(self, user: users.User):
        if self.liked(user):
            raise status.alreadyLiked
        
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

    def unlike(self, user: users.User):
        if not self.liked(user):
            raise status.notLiked

        db.comment_likes.delete_one({
            "comment_id": self.id,
            "user_id": user.id
        })
        events.emit_event("comment_status_updated", user.id, {
            "id": self.id,
            "liked": False
        })
        self.update_stats()

    def edit(self, editor: users.User, content: str):
        if bitfield.has(self.flags, flags.post.protected):
            raise status.postProtected

        if content == self.content:
            return
        
        db.comment_revisions.insert_one({
            "_id": uid.snowflake(),
            "comment_id": self.id,
            "old_content": self.content,
            "new_content": content,
            "editor_id": editor.id,
            "time": uid.timestamp()
        })

        self.flags = bitfield.add(self.flags, flags.comment.edited)
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

def create_comment(post: posts.Post, author: users.User, content: str, parent: Comment = None):
    # Create comment data
    comment = {
        "_id": uid.snowflake(),
        "post_id": post.id,
        "parent_id": (parent.id if parent else None),
        "author_id": author.id,
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

    # Update parent comment
    if parent:
        parent.update_stats()

    # Announce comment creation
    events.emit_event("comment_created", post.id, comment.public)

    # Return comment object
    return comment

def get_comment(comment_id: str, error_on_deleted: bool = True):
    # Get comment from database and check whether it's not found or deleted
    comment = db.post_comments.find_one({"_id": comment_id})
    if comment is None or (error_on_deleted and comment.get("deleted_at")):
        raise status.notFound

    # Return post object
    return Comment(**comment)

def get_post_comments(post: posts.Post, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return comments
    return [Comment(**comment) for comment in db.post_comments.find({"post_id": post.id, "parent_id": None, "deleted_at": None, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

def get_comment_replies(comment: Comment, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return comments
    return [Comment(**comment) for comment in db.post_comments.find({"post_id": comment.post_id, "parent_id": comment.id, "deleted_at": None, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

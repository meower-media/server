from datetime import datetime
from copy import copy
import time
import random

from src.util import status, uid, events, filter, bitfield, flags
from src.entities import users, posts
from src.database import db, redis

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
        likes: int = 0,
        time: datetime = None,
        deleted: bool = False,
        delete_after: datetime = None
    ):
        self.id = _id
        self.post_id = post_id
        self.parent_id = parent_id
        self.author = users.get_user(author_id)
        self.content = content
        self.filtered_content = filtered_content
        self.flags = flags
        self.likes = likes
        self.time = time
        self.deleted = deleted
        self.delete_after = delete_after

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
            "likes": self.likes,
            "time": int(self.time.timestamp()),
            "delete_after": (int(self.delete_after.timestamp()) if (self.delete_after is not None) else None)
        }

    @property
    def admin(self):
        return {
            "id": self.id,
            "author": self.author.partial,
            "content": self.content,
            "filtered_content": self.filtered_content,
            "flags": self.flags,
            "public_flags": self.public_flags,
            "likes": self.likes,
            "time": int(self.time.timestamp()),
            "deleted": self.deleted,
            "delete_after": (int(self.delete_after.timestamp()) if (self.delete_after is not None) else None)
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

    @property
    def reputation(self):
        if bitfield.has(self.flags, flags.post.reputationBanned):
            return 0
        else:
            reputation = ((self.likes + self.meows) - ((time.time() - self.time.timestamp()) ** -5))
            if reputation < 0:
                return 0
            else:
                return reputation

    def count_stats(self, extensive: bool = False):
        if extensive:
            self.likes = db.post_likes.count_documents({"post_id": self.id})
            self.meows = db.post_meows.count_documents({"post_id": self.id})
            self.comments = db.post_comments.count_documents({"post_id": self.id}) 

        db.posts.update_one({"_id": self.id}, {"$set": {
            "likes": self.likes,
            "meows": self.meows, 
            "comments": self.comments,
            "reputation": self.reputation
        }})
        events.emit_event("post_updated", self.id, {
            "id": self.id,
            "likes": self.likes,
            "meows": self.meows,
            "comments": self.comments,
            "reputation": self.reputation
        })

    def liked(self, user: users.User):
        return (db.post_likes.count_documents({"post_id": self.id, "user_id": user.id}) > 0)
    
    def meowed(self, user: users.User):
        return (db.post_meows.count_documents({"post_id": self.id, "user_id": user.id}) > 0)

    def like(self, user: users.User):
        if self.liked(user):
            raise status.alreadyLiked
        
        db.post_likes.insert_one({
            "_id": uid.snowflake(),
            "post_id": self.id,
            "user_id": user.id,
            "time": uid.timestamp()
        })
        events.emit_event("post_status_updated", user.id, {
            "id": self.id,
            "liked": True
        })

        self.likes += 1
        self.count_stats()

    def meow(self, user: users.User):
        if self.meowed(user):
            raise status.alreadyMeowed
        
        db.post_meows.insert_one({
            "_id": uid.snowflake(),
            "post_id": self.id,
            "user_id": user.id,
            "time": uid.timestamp()
        })
        events.emit_event("post_status_updated", user.id, {
            "id": self.id,
            "meowed": True
        })

        self.meows += 1
        self.count_stats()

    def unlike(self, user: users.User):
        if not self.liked(user):
            raise status.notLiked

        db.post_likes.delete_one({
            "post_id": self.id,
            "user_id": user.id
        })
        events.emit_event("post_status_updated", user.id, {
            "id": self.id,
            "liked": False
        })

        self.likes -= 1
        self.count_stats()
    
    def unmeow(self, user: users.User):
        if not self.meowed(user):
            raise status.notMeowed

        db.post_meows.delete_one({
            "post_id": self.id,
            "user_id": user.id
        })
        events.emit_event("post_status_updated", user.id, {
            "id": self.id,
            "meowed": False
        })

        self.meows -= 1
        self.count_stats()

    def edit(self, editor: users.User, content: str, public: bool = True):
        if bitfield.has(self.flags, flags.post.protected):
            raise status.postProtected

        if content == self.content:
            return
        
        db.post_revisions.insert_one({
            "_id": uid.snowflake(),
            "post_id": self.id,
            "old_content": self.content,
            "new_content": content,
            "editor_id": editor.id,
            "public": public,
            "time": uid.timestamp()
        })

        self.flags = bitfield.add(self.flags, flags.post.edited)
        self.content = content
        db.posts.update_one({"_id": self.id}, {"$set": {
            "flags": self.flags,
            "content": self.content
        }})
        events.emit_event("post_updated", self.id, {
            "id": self.id,
            "flags": self.public_flags,
            "content": self.content
        })

    def get_revisions(self, include_private: bool = False):
        query = {"post_id": self.id}
        if not include_private:
            query["public"] = True
        
        revisions = []
        for revision in db.post_revisions.find({"post_id": self.id}):
            revision["id"] = revision["_id"]
            revision["editor"] = users.get_user(revision["editor_id"]).partial
            del revision["_id"]
            del revision["editor_id"]
        return revisions

    def change_revision_privacy(self, revision_id: str, public: bool):
        db.post_revisions.update_one({"_id": revision_id}, {"$set": {"public": public}})
    
    def delete_revision(self, revision_id: str):
        db.post_revisions.delete_one({"_id": revision_id})

    def delete(self, moderated: bool = False, moderation_reason: str = None):
        if self.deleted:
            db.post_revisions.delete_many({"post_id": self.id})
            db.post_likes.delete_many({"post_id": self.id})
            db.post_meows.delete_many({"post_id": self.id})
            db.posts.delete_one({"_id": self.id})
        else:
            self.deleted = True
            self.delete_after = uid.timestamp(epoch=int(time.time() + 1209600))
            db.posts.update_one({"_id": self.id}, {"$set": {"deleted": self.deleted, "delete_after": self.delete_after}})
            events.emit_event("post_deleted", self.id, {
                "id": self.id
            })

def create_comment(post: posts.Post, author: users.User, content: str):
    # Create comment data
    comment = {
        "_id": uid.snowflake(),
        "post_id": post.id,
        "author_id": author.id,
        "content": content,
        "filtered_content": None,
        "time": uid.timestamp(),
        "deleted": False
    }

    # Filter profanity
    filtered_content = filter.censor(content)
    if filtered_content != content:
        comment["filtered_content"] = filtered_content

    # Insert comment into database and convert into Comment object
    db.comments.insert_one(comment)
    comment = Comment(**comment)

    # Announce comment creation
    #events.emit_event("post_created", post.id, post.public)

    # Return comment object
    return comment

def get_comment(comment_id: str, error_on_deleted: bool = True):
    # Get comment from database and check whether it's not found or deleted
    comment = db.comments.find_one({"_id": comment_id})
    if comment is None or (error_on_deleted and comment.get("deleted")):
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

    # Fetch and return all comments
    return [Comment(**comment) for comment in db.comments.find({"post_id": post.id, "deleted": False, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

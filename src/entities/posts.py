from datetime import datetime
from copy import copy
import time
import json

from src.util import status, uid, bitfield, flags
from src.entities import users
from src.database import db, redis

class Post:
    def __init__(
        self,
        _id: str,
        author_id: str = None,
        content: str = None,
        flags: str = 0,
        revisions: list = [],
        likes: int = 0,
        meows: int = 0,
        reputation: int = 0,
        last_counted: datetime = None,
        time: datetime = None,
        deleted: bool = False,
        delete_after: datetime = None
    ):
        self.id = _id
        self.author = users.get_user(author_id)
        self.content = content
        self.flags = flags
        self.revisions = revisions
        self.likes = likes
        self.meows = meows
        self.reputation = reputation
        self.last_counted = last_counted
        self.time = time
        self.deleted = deleted
        self.delete_after = delete_after

    @property
    def public(self):
        return {
            "id": self.id,
            "author": self.author.partial,
            "content": self.content,
            "filtered_content": self.content,  # Need to find a suitable filter
            "flags": self.public_flags,
            "revisions": self.public_revisions,
            "likes": self.likes,
            "meows": self.meows,
            "time": int(self.time.timestamp()),
            "deleted": self.deleted,
            "delete_after": (int(self.delete_after.timestamp()) if (self.delete_after is not None) else None)
        }

    @property
    def admin(self):
        return {
            "id": self.id,
            "author": self.author.partial,
            "content": self.content,
            "filtered_content": self.content,  # Need to find a suitable filter
            "flags": self.flags,
            "revisions": self.admin_revisions,
            "likes": self.likes,
            "meows": self.meows,
            "reputation": self.reputation,
            "last_counted": self.last_counted,
            "time": int(self.time.timestamp()),
            "deleted": self.deleted,
            "delete_after": (int(self.delete_after.timestamp()) if (self.delete_after is not None) else None)
        }

    @property
    def public_flags(self):
        pub_flags = copy(self.flags)
        for flag in [
            flags.post.lockLikes,
            flags.post.lockMeows,
            flags.post.lockReputation
        ]:
            pub_flags = bitfield.remove(pub_flags, flag)
        return pub_flags

    @property
    def public_revisions(self):
        revisions = []
        for revision in self.revisions:
            if revision["public"]:
                revisions.append({
                    "id": revision["id"],
                    "content": revision["content"],
                    "time": revision["time"].timestamp()
                })
        return revisions

    @property
    def admin_revisions(self):
        revisions = []
        for revision in self.revisions:
            revisions.append({
                "id": revision["id"],
                "editor": users.get_user(revision["editor_id"]),
                "content": revision["content"],
                "public": revision["public"],
                "time": revision["time"].timestamp()
            })
        return revisions

    def count_stats(self):
        if not bitfield.has(self.flags, flags.post.lockLikes):
            self.likes = db.reputation.count_documents({"post": self.id, "type": 0})
        
        if not bitfield.has(self.flags, flags.post.lockMeows):
            self.meows = db.reputation.count_documents({"post": self.id, "type": 0})

        if not bitfield.has(self.flags, flags.post.lockReputation):
            self.reputation = ((self.likes + self.meows) - ((time.time() - self.time.timestamp()) ** -5))
            if self.reputation < 0:
                self.reputation = 0

        db.posts.update_one({"_id": self.id}, {"$set": {"likes": self.likes, "meows": self.meows, "reputation": self.reputation}})
        redis.publish("meower:cl", json.dumps({
            "op": "post_updated",
            "post_id": self.id,
            "likes": self.likes,
            "meows": self.meows,
            "reputation": self.reputation
        }))

    def liked(self, user: users.User):
        return (db.reputation.count_documents({"post_id": self.id, "user_id": user.id, "type": 0}) > 0)
    
    def meowed(self, user: users.User):
        return (db.reputation.count_documents({"post_id": self.id, "user_id": user.id, "type": 1}) > 0)

    def like(self, user: users.User):
        if self.liked(user):
            raise status.alreadyLiked
        
        db.reputation.insert_one({
            "_id": uid.snowflake(),
            "post_id": self.id,
            "user_id": user.id,
            "type": 0,
            "time": uid.timestamp()
        })
        redis.publish("meower:cl", json.dumps({
            "op": "post_liked",
            "post_id": self.id,
            "user_id": user.id
        }))

        db.posts.update_one({"_id": self.id}, {"$inc": {"likes": 1}})

    def meow(self, user: users.User):
        if self.meowed(user):
            raise status.alreadyMeowed
        
        db.reputation.insert_one({
            "_id": uid.snowflake(),
            "post_id": self.id,
            "user_id": user.id,
            "type": 1,
            "time": uid.timestamp()
        })
        redis.publish("meower:cl", json.dumps({
            "op": "post_meowed",
            "post_id": self.id,
            "user_id": user.id
        }))

    def unlike(self, user: users.User):
        if not self.liked(user):
            raise status.notLiked

        db.reputation.delete_one({
            "post_id": self.id,
            "user_id": user.id,
            "type": 0
        })
        redis.publish("meower:cl", json.dumps({
            "op": "post_unliked",
            "post_id": self.id,
            "user_id": user.id
        }))
    
    def unmeow(self, user: users.User):
        if not self.meowed(user):
            raise status.notMeowed

        db.reputation.delete_one({
            "post_id": self.id,
            "user_id": user.id,
            "type": 1
        })
        redis.publish("meower:cl", json.dumps({
            "op": "post_unmeowed",
            "post_id": self.id,
            "user_id": user.id
        }))

    def edit(self, editor: users.User, content: str, public: bool = True):
        if bitfield.has(self.flags, flags.post.protected):
            raise status.postProtected
        
        self.flags = bitfield.add(self.flags, flags.post.edited)
        self.revisions.append({
            "id": uid.snowflake(),
            "editor_id": editor.id,
            "content": self.content,            
            "public": public,
            "time": uid.timestamp()
        })
        self.content = content
        db.posts.update_one({"_id": self.id}, {"$set": {
            "flags": self.flags,
            "content": self.content,
            "revisions": self.revisions
        }})
        redis.publish("meower:cl", json.dumps({
            "op": "post_updated",
            "post_id": self.id,
            "content": self.content,
            "revisions": self.public_revisions
        }))

    def change_revision_privacy(self, revision_id: str, public: bool = True):
        for revision in self.revisions:
            if revision["id"] == revision_id:
                revision["public"] = public
        db.posts.update_one({"_id": self.id}, {"$set": {"revisions": self.revisions}})
        redis.publish("meower:cl", json.dumps({
            "op": "post_updated",
            "post_id": self.id,
            "revisions": self.public_revisions
        }))
    
    def delete_revision(self, revision_id: str):
        for revision in self.revisions:
            if revision["id"] == revision_id:
                self.revisions.remove(revision)

    def delete(self, moderated: bool = False, moderation_reason: str = None):
        self.deleted = True
        self.delete_after = uid.timestamp(epoch=(time.time() + 1209600))
        db.posts.update_one({"_id": self.id}, {"$set": {"deleted": self.deleted, "delete_after": self.delete_after}})
        redis.publish("meower:cl", json.dumps({
            "op": "post_deleted",
            "post_id": self.id
        }))

def create_post(author: users.User, content: str, delete_after: datetime = None):
    post = {
        "_id": uid.snowflake(),
        "author_id": author.id,
        "content": content,
        "time": uid.timestamp(),
        "deleted": False
    }

    if delete_after is not None:
        post["delete_after"] = delete_after

    db.posts.insert_one(post)
    post = Post(**post)
    redis.publish("meower:cl", json.dumps({
        "op": "post_created",
        "post": post.public
    }))
    return post

def get_post(post_id: str, error_on_deleted: bool = True):
    post = db.posts.find_one({"_id": post_id})
    if post is None or (error_on_deleted and post.get("deleted")):
        raise status.notFound

    return Post(**post)

def get_feed(user: users.User, before: str = None, after: str = None, limit: int = 25):
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    following = [relation["user_id"] for relation in user.get_relations(state=1)]
    meowed_posts = [meow["post_id"] for meow in db.meows.find({"user_id": {"$in": following}, "_id": id_range}, sort=[("_id", -1)], limit=limit, projection={"post_id": 1})]

    query = {
        "$or": [
            {
                "deleted": False,
                "_id": id_range
            },
            {
                "deleted": False,
                "author_id": {"$in": following},
                "_id": id_range
            }
        ]
    }
    query["$or"][0]["_id"]["$in"] = meowed_posts
    
    return [Post(**post) for post in db.posts.find(query, sort=[("_id", -1)], limit=limit)]

def get_latest_posts(before: str = None, after: str = None, limit: int = 25):
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    return [Post(**post) for post in db.posts.find({"deleted": False, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

def get_top_posts(before: str = None, after: str = None, limit: int = 25):
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    return [Post(**post) for post in db.posts.find({"deleted": False, "_id": id_range}, sort=[("reputation", -1)], limit=limit)]

def search_posts(query: str, before: str = None, after: str = None, limit: int = 25):
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    return [Post(**post) for post in db.posts.find({"deleted": False, "$text": {"$search": query}, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

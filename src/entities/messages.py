from datetime import datetime
from copy import copy
import time
import json

from src.util import status, uid, bitfield, flags
from src.entities import users
from src.database import db, redis

class Message:
    def __init__(
        self,
        _id: str,
        author_id: str = None,
        content: str = None,
        flags: str = 0,
        likes: int = 0,
        time: datetime = None,
        deleted: bool = False,
        delete_after: datetime = None
    ):
        self.id = _id
        self.author = users.get_user(author_id)
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
            "author": self.author.partial,
            "content": self.content,
            "filtered_content": self.content,  # Need to find a suitable filter, may end up being client-side
            "flags": self.public_flags,
            "likes": self.likes,
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
            "likes": self.likes,
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
        self.delete_after = uid.timestamp(epoch=int(time.time() + 1209600))
        db.posts.update_one({"_id": self.id}, {"$set": {"deleted": self.deleted, "delete_after": self.delete_after}})
        redis.publish("meower:cl", json.dumps({
            "op": "post_deleted",
            "post_id": self.id
        }))

def create_post(author: users.User, content: str):
    # Create post data
    post = {
        "_id": uid.snowflake(),
        "author_id": author.id,
        "content": content,
        "time": uid.timestamp(),
        "deleted": False
    }

    # Insert post into database and convert into Post object
    db.posts.insert_one(post)
    post = Post(**post)

    # Announce post creation
    redis.publish("meower:cl", json.dumps({
        "op": "post_created",
        "post": post.public
    }))

    # Return post object
    return post

def get_post(post_id: str, error_on_deleted: bool = True):
    # Get post from database and check whether it's not found or deleted
    post = db.posts.find_one({"_id": post_id})
    if post is None or (error_on_deleted and post.get("deleted")):
        raise status.notFound

    # Return post object
    return Post(**post)

def get_feed(user: users.User, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Get following list and posts that the user's followers have meowed
    following = [relation["to"] for relation in user.get_relationships(1)]
    meowed_posts = [meow["post_id"] for meow in db.meows.find({"user_id": {"$in": following}, "_id": id_range}, sort=[("_id", -1)], limit=limit, projection={"post_id": 1})]

    # Create query
    query = {
        "$or": [
            {
                "deleted": False,
                "_id": copy(id_range)
            },
            {
                "deleted": False,
                "author_id": {"$in": following},
                "_id": copy(id_range)
            }
        ]
    }
    query["$or"][0]["_id"]["$in"] = meowed_posts
    
    # Fetch and return all posts
    return [Post(**post) for post in db.posts.find(query, sort=[("_id", -1)], limit=limit)]

def get_latest_posts(before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all posts
    return [Post(**post) for post in db.posts.find({"deleted": False, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

def get_top_posts(before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all posts
    return [Post(**post) for post in db.posts.find({"deleted": False, "_id": id_range}, sort=[("reputation", -1)], limit=limit)]

def search_posts(query: str, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all posts
    return [Post(**post) for post in db.posts.find({"deleted": False, "$text": {"$search": query}, "_id": id_range}, sort=[("_id", -1)], limit=limit)]

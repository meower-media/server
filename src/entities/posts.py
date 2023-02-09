from datetime import datetime
from copy import copy
from threading import Thread
import time
import random

from src.util import status, uid, events, filter, bitfield, flags
from src.entities import users, notifications
from src.database import db, redis

class Post:
    def __init__(
        self,
        _id: str,
        author_id: str,
        content: str = None,
        filtered_content: str = None,
        flags: str = 0,
        stats: dict = {
            "likes": 0,
            "meows": 0,
            "comments": 0
        },
        top_stats: dict = {
            "likes": 0,
            "meows": 0,
            "comments": 0
        },
        reputation: int = 0,
        reputation_last_counted: datetime = None,
        time: datetime = None,
        delete_after: datetime = None,
        deleted_at: datetime = None
    ):
        self.id = _id
        self.author = users.get_user(author_id)
        self.content = content
        self.filtered_content = filtered_content
        self.flags = flags
        self.stats = stats
        self.top_stats = top_stats
        self.reputation_last_counted = reputation_last_counted
        self.time = time
        self.delete_after = delete_after
        self.deleted_at = deleted_at

    @property
    def public(self):
        return {
            "id": self.id,
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
            "author": self.author.partial,
            "content": self.content,
            "filtered_content": self.filtered_content,
            "flags": self.flags,
            "public_flags": self.public_flags,
            "stats": self.stats,
            "top_stats": self.top_stats,
            "time": int(self.time.timestamp()),
            "delete_after": (int(self.delete_after.timestamp()) if self.delete_after else None),
            "deleted_at": (int(self.deleted_at.timestamp()) if self.deleted_at else None)
        }

    @property
    def legacy(self):
        return {
            "_id": self.id,
            "type": 1,
            "post_origin": "home",
            "u": self.author.username,
            "t": uid.timestamp(epoch=int(self.time.timestamp()), jsonify=True),
            "p": (self.filtered_content if self.filtered_content else self.content),
            "post_id": self.id,
            "isDeleted": (self.deleted_at is not None)
        }

    @property
    def public_flags(self):
        pub_flags = copy(self.flags)
        for flag in [
            flags.posts.reputationBanned
        ]:
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
        self.reputation_last_counted = uid.timestamp()
        if bitfield.has(self.flags, flags.posts.reputationBanned) or (time.time() > (time.time()+2592000)):
            return 0
        else:
            reputation = ((self.stats.get("likes", 0) + self.stats.get("meows", 0)) - ((time.time() - self.time.timestamp()) ** -5))
            if reputation < 0:
                return 0
            else:
                return reputation

    def update_stats(self):
        def run():
            self.stats = {
                "likes": db.post_likes.count_documents({"post_id": self.id}),
                "meows": db.post_meows.count_documents({"post_id": self.id}),
                "comments": db.post_comments.count_documents({"post_id": self.id, "deleted_at": None})
            }
            for key, val in self.stats.items():
                if val > self.top_stats.get(key, 0):
                    for milestone in [5, 10, 25, 50, 100, 1000]:
                        if (val >= milestone) and (self.top_stats.get(key, 0) < milestone):
                            if key == "likes":
                                if bitfield.has(self.author.config.get("notifications", 127), flags.configNotifications.postLikes):
                                    notifications.create_notification(self.author, 2, {
                                        "post_id": self.id,
                                        "milestone": milestone
                                    })
                            elif key == "meows":
                                if bitfield.has(self.author.config.get("notifications", 127), flags.configNotifications.postMeows):
                                    notifications.create_notification(self.author, 3, {
                                        "post_id": self.id,
                                        "milestone": milestone
                                    })

                    self.top_stats.update({key: val})

            db.posts.update_one({"_id": self.id}, {"$set": {
                "stats": self.stats,
                "top_stats": self.top_stats,
                "reputation": self.reputation,
                "reputation_last_counted": self.reputation_last_counted
            }})
            events.emit_event("post_updated", self.id, {
                "id": self.id,
                "stats": self.stats
            })
        Thread(target=run).start()

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
        self.update_stats()

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
        self.update_stats()

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
        self.update_stats()
    
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
        self.update_stats()

    def edit(self, editor: users.User, content: str, public: bool = True):
        if bitfield.has(self.flags, flags.posts.protected):
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

        self.flags = bitfield.add(self.flags, flags.posts.edited)
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
        for revision in db.post_revisions.find(query):
            revision["id"] = revision["_id"]
            revision["editor"] = users.get_user(revision["editor_id"]).partial
            del revision["_id"]
            del revision["editor_id"]
        return revisions

    def change_revision_privacy(self, revision_id: str, public: bool):
        db.post_revisions.update_one({"_id": revision_id}, {"$set": {"public": public}})
    
    def delete_revision(self, revision_id: str):
        db.post_revisions.delete_one({"_id": revision_id})

    def delete(self):
        self.deleted_at = uid.timestamp()
        db.posts.update_one({"_id": self.id}, {"$set": {"deleted_at": self.deleted_at}})
        events.emit_event("post_deleted", self.id, {
            "id": self.id
        })
        self.author.update_stats()

def create_post(author: users.User, content: str):
    # Create post data
    post = {
        "_id": uid.snowflake(),
        "author_id": author.id,
        "content": content,
        "filtered_content": None,
        "time": uid.timestamp(),
        #"deleted_at": None
    }

    # Filter profanity
    filtered_content = filter.censor(content)
    if filtered_content != content:
        post["filtered_content"] = filtered_content

    # Insert post into database and convert into Post object
    db.posts.insert_one(post)
    post = Post(**post)

    # Announce post creation
    events.emit_event("post_created", post.id, post.public)

    # Add post ID to latest posts list
    redis.lpush("latest_posts", post.id)
    redis.ltrim("latest_posts", 0, 9999)

    # Update user stats
    post.author.update_stats()

    # Return post object
    return post

def get_post(post_id: str, error_on_deleted: bool = True):
    # Get post from database and check whether it's not found or deleted
    post = db.posts.find_one({"_id": post_id})
    if post is None or (error_on_deleted and post.get("deleted_at")):
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
    following = user.get_following_ids()
    meowed_posts = [meow["post_id"] for meow in db.post_meows.find({"user_id": {"$in": following}, "post_id": id_range}, sort=[("post_id", -1)], limit=limit, projection={"post_id": 1})]

    # Create query
    query = {
        "$or": [
            {
                "deleted_at": None,
                "_id": copy(id_range)
            },
            {
                "deleted_at": None,
                "author_id": {"$in": following},
                "_id": copy(id_range)
            }
        ]
    }
    query["$or"][0]["_id"]["$in"] = meowed_posts

    # Primary fetch
    fetched_posts = [Post(**post) for post in db.posts.find(query, sort=[("_id", -1)], limit=limit)]

    # Secondary fetch to fill results
    if len(fetched_posts) < limit:
        total_latest_posts = redis.llen("latest_posts")
        attempts = 0
        while (len(fetched_posts) < limit) and (len(fetched_posts) < total_latest_posts):
            # Have an attempt limit so we don't get stuck in an infinite loop
            if attempts >= 3:
                break
            else:
                attempts += 1
            
            # Get random posts from latest posts list
            for i in range(limit-len(fetched_posts)):
                random_index = random.randint(0, total_latest_posts-1)
                post_id = redis.lrange("latest_posts", random_index, random_index)[0].decode()
                fetched_posts.insert(random.randint(0, len(fetched_posts)), get_post(post_id, error_on_deleted=False))

            # Cleanup deleted and duplicates posts
            post_ids = set()
            for post in copy(fetched_posts):
                if post.deleted_at or (post.id in post_ids):
                    fetched_posts.remove(post)
                    continue
                post_ids.add(post.id)

    # Return fetched posts
    return fetched_posts

def get_latest_posts(before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all posts
    return [Post(**post) for post in db.posts.find({"deleted_at": None, "_id": id_range}, sort=[("time", -1)], limit=limit)]

def get_top_posts(before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all posts
    return [Post(**post) for post in db.posts.find({"deleted_at": None, "_id": id_range}, sort=[("reputation", -1)], limit=limit)]

def search_posts(query: str, before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all posts
    return [Post(**post) for post in db.posts.find({"deleted_at": None, "$text": {"$search": query}, "_id": id_range}, sort=[("time", -1)], limit=limit)]

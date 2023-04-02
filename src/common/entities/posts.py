import time

from src.common.entities import users, chats, reports, audit_log
from src.common.util import uid, errors, events, profanity
from src.common.database import db, count_pages


class Post:
    def __init__(
        self,
        _id: str,
        type: int,
        origin: str,
        author: str,
        time: int,
        content: str,
        unfiltered_content: str = None,
        deleted_at: int = None,
        mod_deleted: bool = False
    ):
        self.id = _id
        self.type = type
        self.origin = origin
        self.author = author
        self.time = time
        self.content = content
        self.unfiltered_content = unfiltered_content
        self.deleted_at = deleted_at
        self.mod_deleted = mod_deleted

    @property
    def public(self):
        return {
            "_id": self.id,
            "post_id": self.id,
            "type": self.type,
            "post_origin": self.origin,
            "u": self.author,
            "t": uid.timestamp(epoch=self.time, jsonify=True),
            "p": self.content,
            "unfiltered_p": self.unfiltered_content,
            "isDeleted": (self.deleted_at is not None)
        }
    
    def has_access(self, user):
        # Default permissions if a user isn't specified
        if not user:
            return ((self.origin == "home") and (not self.deleted_at))

        # Get user
        if isinstance(user, str):
            user = users.get_user(user)

        # Check user level
        if user.lvl >= 1:
            return True

        # Check if post is deleted
        if self.deleted_at:
            return False
        
        # Check if user has access to chat
        if self.origin == "home":
            return True
        else:
            chat = chats.get_chat(self.origin)
            return (user.username in chat.members)

    def edit(self, new_content: str):
        # Set properties
        self.content = profanity.censor(new_content)
        self.unfiltered_content = (None if (self.content == new_content) else new_content)
        db.posts.update_one({"_id": self.id}, {"$set": {
            "content": self.content,
            "unfiltered_content": self.unfiltered_content
        }})

        # Send post update event
        events.send_event("update_post", self.public)

    def delete(self, actor: str):
        # Set properties
        self.deleted_at = int(time.time())
        self.mod_deleted = (actor != self.author)
        db.posts.update_one({"_id": self.id}, {"$set": {
            "deleted_at": self.deleted_at,
            "mod_deleted": self.mod_deleted
        }})

        # Send post update event
        events.send_event("update_post", self.public)
        
        if self.mod_deleted:
            # Close report
            try:
                report = reports.get_report(self.id)
            except errors.NotFound:
                pass
            else:
                report.close(True)

            # Create audit log item
            audit_log.create_log("delete_post", actor, {"id": self.id})

    def restore(self):
        # Set properties
        self.deleted_at = None
        self.mod_deleted = False
        db.posts.update_one({"_id": self.id}, {"$unset": {
            "deleted_at": "",
            "mod_deleted": ""
        }})

        # Send post update event
        events.send_event("update_post", self.public)


def create_post(origin: str, author: str, content: str) -> Post:
    # Create post data
    post_data = {
        "_id": uid.uuid(),
        "type": 1,
        "origin": origin,
        "author": author,
        "time": int(time.time()),
        "content": content
    }

    # Filter content
    post_data["content"] = profanity.censor(content)
    if post_data["content"] != content:
        post_data["unfiltered_content"] = content
    
    # Insert post into database
    if origin != "livechat":
        db.posts.insert_one(post_data)

    # Get post object
    post = Post(**post_data)

    # Send post creation event
    events.send_event("create_post", post.public)

    # Return post object
    return post


def create_inbox_message(username: str, content: str) -> Post:
    # Create post data
    post_data = {
        "_id": uid.uuid(),
        "type": 2,
        "origin": "inbox",
        "author": username,
        "time": int(time.time()),
        "content": content
    }

    # Insert post into database
    db.posts.insert_one(post_data)

    # Update user
    db.users.update_many({"_id": username}, {"$set": {"unread_inbox": True}})

    # Get post object
    post = Post(**post_data)

    # Send post creation event
    events.send_event("create_post", post.public)

    # Return post object
    return post


def create_announcement(content: str) -> Post:
    # Create post data
    post_data = {
        "_id": uid.uuid(),
        "type": 2,
        "origin": "inbox",
        "author": "Server",
        "time": int(time.time()),
        "content": content
    }

    # Insert post into database
    db.posts.insert_one(post_data)

    # Update users
    db.users.update_many({}, {"$set": {"unread_inbox": True}})

    # Get post object
    post = Post(**post_data)

    # Send post creation event
    events.send_event("create_post", post.public)

    # Return post object
    return post


def get_post(post_id: str) -> Post:
    # Get post from database
    post = db.posts.find_one({"_id": post_id})

    # Return post object
    if post:
        return Post(**post)
    else:
        raise errors.NotFound


def get_posts(origin: str, author: str = None, page: int = 1) -> list[Post]:
    query = {
        "origin": origin,
        "deleted_at": None
    }
    if author:
        query["author"] = author
    return count_pages("posts", query), [Post(**post) for post in db.posts.find(query,
                                                   sort=[("time", -1)],
                                                   skip=((page-1)*25),
                                                   limit=25)]


def search_posts(origin: str, content_query: str = None, page: int = 1) -> list[Post]:
    query = {
        "origin": origin,
        "deleted_at": None,
        "$text": {"$search": content_query}
    }
    return count_pages("posts", query), [Post(**post) for post in db.posts.find(query,
                                                   sort=[("time", -1)],
                                                   skip=((page-1)*25),
                                                   limit=25)]


def get_inbox_messages(username: str, page: int = 1) -> list[Post]:
    query = {
        "origin": "inbox",
        "deleted_at": None,
        "author": {"$in": [username, "Server"]}
    }
    return count_pages("posts", query), [Post(**post) for post in db.posts.find(query,
                                                   sort=[("time", -1)],
                                                   skip=((page-1)*25),
                                                   limit=25)]

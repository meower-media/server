from threading import Thread
from typing import Optional, Iterable, Any
import uuid, time, msgpack, pymongo

from cloudlink import CloudlinkServer
from database import db, rdb
from utils import timestamp
from uploads import FileDetails

"""
Meower Supporter Module
This module provides constant variables, and other miscellaneous supporter utilities.
"""

class Supporter:
    def __init__(self, cl: CloudlinkServer):
        # CL server
        self.cl = cl

        # Set status
        status = db.config.find_one({"_id": "status"})
        self.repair_mode = status["repair_mode"]
        self.registration = status["registration"]

        # Start admin pub/sub listener
        Thread(target=self.listen_for_admin_pubsub, daemon=True).start()

    def get_chats(self, username: str) -> list[dict[str, Any]]:
        # Get active DMs and favorited chats
        user_settings = db.user_settings.find_one({"_id": username}, projection={
            "active_dms": 1,
            "favorited_chats": 1
        })
        if not user_settings:
            user_settings = {
                "active_dms": [],
                "favorited_chats": []
            }
        if "active_dms" not in user_settings:
            user_settings["active_dms"] = []
        if "favorited_chats" not in user_settings:
            user_settings["favorited_chats"] = []

        # Get and return chats
        return list(db.chats.find({"$or": [
            {  # DMs
                "_id": {
                    "$in": user_settings["active_dms"] + user_settings["favorited_chats"]
                },
                "members": username,
                "deleted": False
            },
            {  # group chats
                "members": username,
                "type": 0,
                "deleted": False
            }
        ]}))

    def create_post(
        self,
        origin: str,
        author: str,
        content: str,
        attachments: list[FileDetails] = [],
        nonce: Optional[str] = None,
        chat_members: list[str] = [],
        reply_to: list[str] = []
    ) -> tuple[bool, dict]:
        # Create post ID and get timestamp
        post_id = str(uuid.uuid4())
        ts = timestamp(1).copy()

        # Make sure replied to posts exist
        for reply in reply_to:
            if not db.posts.count_documents({
                "_id": reply,
                "post_origin": origin
            }, limit=1):
                reply_to.remove(reply)

        # Construct post object
        post = {
            "_id": post_id,
            "post_origin": origin, 
            "u": author,
            "t": ts, 
            "p": content,
            "attachments": attachments,
            "isDeleted": False,
            "pinned": False,
            "reply_to": reply_to,
            "reactions": []
        }

        # Add database item
        if origin != "livechat":
            db.posts.insert_one(post)

        # Add nonce for WebSocket
        if nonce:
            post["nonce"] = nonce

        # Send live packet
        if origin == "inbox":
            self.cl.send_event("inbox_message", post, usernames=(None if author == "Server" else [author]))
        else:
            self.cl.send_event("post", post, usernames=(None if origin in ["home", "livechat"] else chat_members))

        # Update other database items
        if origin == "inbox":
            if author == "Server":
                db.user_settings.update_many({}, {"$set": {"unread_inbox": True}})
            else:
                db.user_settings.update_one({"_id": author}, {"$set": {"unread_inbox": True}})
        elif origin != "home":
            db.chats.update_one({"_id": origin}, {"$set": {"last_active": int(time.time())}})

        # Return post
        return post

    def listen_for_admin_pubsub(self):
        pubsub = rdb.pubsub()
        pubsub.subscribe("admin")
        for msg in pubsub.listen():
            try:
                msg = msgpack.loads(msg["data"])
                match msg.pop("op"):
                    case "alert_user":
                        self.create_post("inbox", msg["user"], msg["content"])
                    case "ban_user":
                        # Get user details
                        username = msg.pop("user")
                        user = db.usersv0.find_one({"_id": username}, projection={"uuid": 1, "ban": 1})
                        if not user:
                            continue

                        # Construct ban state
                        ban_state = {
                            "state": msg.get("state", user["ban"]["state"]),
                            "restrictions": msg.get("restrictions", user["ban"]["restrictions"]),
                            "expires": msg.get("expires", user["ban"]["expires"]),  
                            "reason": msg.get("reason", user["ban"]["reason"]),
                        }

                        # Set new ban state
                        db.usersv0.update_one({"_id": username}, {"$set": {"ban": ban_state}})

                        # Add note to admin notes
                        if "note" in msg:
                            notes = db.admin_notes.find_one({"_id": user["uuid"]})
                            if notes and notes["notes"] != "":
                                msg["note"] = notes["notes"] + "\n\n" + msg["note"]
                            db.admin_notes.update_one({"_id": user["uuid"]}, {"$set": {
                                "notes": msg["note"],
                                "last_modified_by": "Server",
                                "last_modified_at": int(time.time())
                            }}, upsert=True)

                        # Logout user (can't kick because of async stuff)
                        for c in self.cl.usernames.get(username, []):
                            c.logout()
            except:
                continue

    def parse_posts_v0(
        self, 
        posts: Iterable[dict[str, Any]],
        requester: Optional[str] = None,
        include_replies: bool = True,
        include_revisions: bool = False
    ) -> Iterable[dict[str, Any]]:
        for post in posts:
            if not post:
                continue

            # Stupid legacy stuff
            post.update({
                "type": 2 if post["post_origin"] == "inbox" else 1,
                "post_id": post["_id"]
            })

            # Author
            post.update({"author": db.usersv0.find_one({"_id": post["u"]}, projection={
                "_id": 1,
                "uuid": 1,
                "flags": 1,
                "pfp_data": 1,
                "avatar": 1,
                "avatar_color": 1
            })})

            # Replies
            if include_replies:
                post.update({"reply_to": [
                    self.parse_posts_v0([db.posts.find_one({
                        "_id": post_id,
                        "post_origin": post["post_origin"],
                        "isDeleted": {"$ne": True}
                    })], include_replies=False)[0] for post_id in post.pop("reply_to", [])
                ]})
            else:
                post.update({"reply_to": [None for _ in post.pop("reply_to", [])]})

            # Reactions
            [reaction.update({
                "user_reacted": (db.post_reactions.count_documents({"_id": {
                    "post_id": post["_id"],
                    "emoji": reaction["emoji"],
                    "user": requester
                }}, limit=1) > 0) if requester else False
            }) for reaction in post.get("reactions", [])]

            # Revisions
            if include_revisions:
                post.update({
                    "revisions": list(db.post_revisions.find(
                        {"post_id": post["_id"]},
                        sort=[("time", pymongo.DESCENDING)]
                    ))
                })

        return posts

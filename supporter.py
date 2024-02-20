from better_profanity import profanity
import uuid
import time

from cloudlink import CloudlinkServer, CloudlinkClient
from database import db, blocked_ips
from utils import timestamp

"""
Meower Supporter Module
This module provides constant variables, profanity filtering, and other miscellaneous supporter utilities.
"""

class Supporter:
    def __init__(self, cl: CloudlinkServer):
        # CL server
        self.cl = cl
        self.cl.add_callback("on_open", self.on_open)
        self.cl.add_callback("on_close", self.on_close)
        for code, details in {
            "PasswordInvalid": "I:011 | Invalid Password",
            "IDExists": "I:015 | Account exists",
            "MissingPermissions": "I:017 | Missing permissions",
            "Banned": "E:018 | Account Banned",
            "IllegalChars": "E:019 | Illegal characters detected",
            "Kicked": "E:020 | Kicked",
            "ChatFull": "E:023 | Chat full",
            "LoggedOut": "I:024 | Logged out",
            "Deleted": "E:025 | Deleted",
            "UserBanned": "E:026 | User banned"
        }.items():
            self.cl.add_statuscode(code, details)

        # Constant vars
        self.repair_mode = True
        self.registration = False
        self.filter = {
            "whitelist": [],
            "blacklist": []
        }

        # Set status
        status = db.config.find_one({"_id": "status"})
        self.repair_mode = status["repair_mode"]
        self.registration = status["registration"]

        # Set filter
        self.filter = db.config.find_one({"_id": "filter"})
    
    async def on_open(self, client: CloudlinkClient):
        if self.repair_mode or blocked_ips.search_best(client.ip):
            client.kick(statuscode="Blocked")

    async def on_close(self, client: CloudlinkClient):
        if client.username:
            db.usersv0.update_one({"_id": client.username, "last_seen": {"$ne": None}}, {"$set": {
                "last_seen": int(time.time())
            }})
    
    def wordfilter(self, message: str) -> str:
        profanity.load_censor_words(whitelist_words=self.filter["whitelist"])
        message = profanity.censor(message)
        profanity.load_censor_words(whitelist_words=self.filter["whitelist"], custom_words=self.filter["blacklist"])
        message = profanity.censor(message)
        return message

    def create_post(self, origin: str, author: str, content: str, chat_members: list[str] = []) -> (bool, dict):
        # Create post ID and get timestamp
        post_id = str(uuid.uuid4())
        ts = timestamp(1).copy()

        # Construct post object
        post = {
            "_id": post_id,
            "type": 2 if origin == "inbox" else 1,
            "post_origin": origin, 
            "u": author,
            "t": ts, 
            "p": content,
            "post_id": post_id, 
            "isDeleted": False
        }
        
        # Profanity filter
        filtered_content = self.wordfilter(content)
        if filtered_content != content:
            post["p"] = filtered_content
            post["unfiltered_p"] = content

        # Add database item
        if origin != "livechat":
            db.posts.insert_one(post)

        # Add database item and send live packet
        if origin == "home":
            self.cl.broadcast({"mode": 1, **post}, direct_wrap=True)
        elif origin == "inbox":
            if author == "Server":
                db.user_settings.update_many({}, {"$set": {"unread_inbox": True}})
            else:
                db.user_settings.update_one({"_id": author}, {"$set": {"unread_inbox": True}})

            self.cl.broadcast({
                "mode": "inbox_message",
                "payload": post
            }, direct_wrap=True, usernames=(None if author == "Server" else [author]))
        elif origin == "livechat":
            self.cl.broadcast({"state": 2, **post}, direct_wrap=True)
        else:
            db.chats.update_one({"_id": origin}, {"$set": {"last_active": int(time.time())}})
            self.cl.broadcast({"state": 2, **post}, direct_wrap=True, usernames=chat_members)
        
        # Return post
        return post

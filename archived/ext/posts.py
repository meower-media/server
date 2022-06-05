import time
from uuid import uuid4

"""

Meower Posts Module

This module provides the ability to create and read posts.
This keeps other files clean and allows both the API and WSS to use the same functions.

"""

class Posts:
    def __init__(self, meower):
        self.meower = meower
        self.log = meower.supporter.log

        self.log("Posts initialized!")
    
    def get_post(self, post_id, requested_by="Server", ignore_deletion=False):
        FileRead, postdata = self.meower.files.load_item("posts", post_id)
        if not FileRead:
            return False, False, None

        # Check for permission
        has_permission = False
        if postdata["post_origin"] == "home":
            has_permission = True
        elif postdata["post_origin"] == "inbox":
            if (postdata["u"] == requested_by) or (postdata["u"] == "Server"):
                has_permission = True
        else:
            # Get chat data
            FileRead, chatdata = self.meower.files.load_item("chats", postdata["post_origin"])
            if not FileRead:
                return False, False, None
            if (requested_by in chatdata["members"]) or (requested_by == "Server"):
                has_permission = True
        
        # Create post payload
        if postdata["isDeleted"] and (not ignore_deletion):
            payload = {"isDeleted": True}
        else:
            payload = postdata

        return True, has_permission, postdata

    def create_post(self, origin, author, content, link_to=None, parent_post=None):
        postdata = {
            "post_origin": origin,
            "u": author,
            "t": self.meower.timestamp(1),
            "p": content,
            "link": link_to,
            "parent": parent_post,
            "isDeleted": False
        }
        FileWrite = self.meower.files.create_item("posts", str(uuid4()), postdata)
        if not FileWrite:
            return False, None
        
        if postdata["post_origin"] == "inbox":
            if postdata["u"] == "Server":
                self.meower.files.update_all("usersv0", {"unread_inbox": False}, {"unread_inbox": True})
            else:
                self.meower.accounts.update_config(postdata["u"], {"unread_inbox": True})

        if (postdata["post_origin"] == "home") or (postdata["post_origin"] == "livechat"):
            self.meower.ws.sendPayload("post", postdata)
        elif (postdata["post_origin"] == "inbox") and (postdata["u"] == "Server"):
            self.meower.ws.sendPayload("new_inbox", "")
        elif postdata["post_origin"] == "inbox":
            self.meower.ws.sendPayload("new_inbox", "", username=postdata["u"])
        else:
            pass # group chats

        return True, postdata
    
    def update_statedata(self, chat, user, state):
        postdata = {
            "u": user,
            "state": state
        }

        payload = {
            "mode": "state",
            "payload": postdata
        }

        if postdata["post_origin"] == "livechat":
            self.sendPacket({"cmd": "direct", "val": payload})
            return True
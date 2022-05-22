import time
from uuid import uuid4

"""

Meower Posts Module

This module provides the ability to create and read posts.
This keeps other files clean and allows both the API and WSS to use the same functions.

"""

class Posts:
    def __init__(self, meower):
        self.cl = meower.cl
        self.log = meower.supporter.log
        self.errorhandler = meower.supporter.full_stack
        self.timestamp = meower.supporter.timestamp
        self.sendPacket = meower.supporter.sendPacket
        self.files = meower.files
        self.log("Posts initialized!")
    
    def get_post(self, post_id, requested_by="Server", ignore_deletion=False):
        FileRead, postdata = self.files.load_item("posts", post_id)
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
            FileRead, chatdata = self.files.load_item("chats", postdata["post_origin"])
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
        chatdata = {
            "post_origin": origin,
            "u": author,
            "t": self.timestamp(1),
            "p": content,
            "link": link_to,
            "parent": parent_post,
            "isDeleted": False
        }
        FileWrite = self.files.write_item("posts", str(uuid4()), chatdata)
        if not FileWrite:
            return False, chatdata
        
        if (chatdata["post_origin"] == "home") or (chatdata["post_origin"] == "livechat") or ((chatdata["post_origin"] == "inbox") and (chatdata["u"] == "Server")):
            payload = {
                "mode": "post",
                "payload": chatdata
            }
            self.sendPacket({"cmd": "direct", "val": payload})
    
    def update_statedata(self, chat, user, state):
        payload = {
            "mode": "statedata",
            "payload": {
                "u": user,
                "state": state
            }
        }

        self.sendPacket({"cmd": "direct", "val": payload})
        return True
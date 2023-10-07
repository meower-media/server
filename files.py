from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
import time
import os

from security import Permissions

"""

Meower Files Module

This module provides filesystem functionality and a primitive JSON-file based database interface.
This file should be modified/refactored to interact with a JSON-friendly database server instead of filesystem directories and files.

"""

load_dotenv()


class Files:
    def __init__(self, logger, errorhandler):
        self.log = logger
        self.errorhandler = errorhandler

        self.log("Connecting to database...")
        try:
            self.db = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"))[os.getenv("MONGO_DB", "meowerserver")]
            self.db.command("ping")
        except Exception as e:
            self.log(f"Failed connecting to database: {e}")
            exit()
        else:
            self.log("Connected to database!")

        # Check connection status
        if self.db.client.get_database("meowerserver") == None:
            self.log("Failed to connect to MongoDB database!")
        else:
            self.log("Connected to database")

        # Create database collections
        for item in {
            "config",
            "usersv0",
            "user_settings",
            "netlog",
            "relationships",
            "posts",
            "post_revisions",
            "chats",
            "reports",
            "admin_notes",
            "audit_log"
        }:
            if item not in self.db.list_collection_names():
                self.log("Creating collection {0}".format(item))
                self.db.create_collection(name=item)

        # Create collection indexes
        try:
            self.db["usersv0"].create_index(
                [("lower_username", ASCENDING), ("created", DESCENDING)],
                name="lower_username",
            )
        except: pass
        try:
            self.db["netlog"].create_index([("users", ASCENDING)], name="users")
        except: pass
        try:
            self.db["netlog"].create_index(
                [("last_active", ASCENDING)],
                name="last_active_ttl",
                expireAfterSeconds=7776000,
                partialFilterExpression={"banned": False},
            )
        except: pass
        try:
            self.db["netlog"].create_index(
                [("banned", ASCENDING)],
                name="banned",
                partialFilterExpression={"banned": True},
            )
        except: pass
        try:
            self.db["posts"].create_index(
                [
                    ("post_origin", ASCENDING),
                    ("isDeleted", ASCENDING),
                    ("t.e", DESCENDING),
                    ("u", ASCENDING),
                ],
                name="default"
            )
        except: pass
        try:
            self.db["posts"].create_index(
                [
                    ("post_origin", ASCENDING),
                    ("isDeleted", ASCENDING),
                    ("p", TEXT),
                    ("t.e", DESCENDING),
                ],
                name="search",
                partialFilterExpression={"post_origin": "home", "isDeleted": False},
            )
        except: pass
        try:
            self.db["posts"].create_index(
                [("deleted_at", ASCENDING)],
                name="deleted_at_ttl",
                expireAfterSeconds=2592000,
                partialFilterExpression={"isDeleted": True, "mod_deleted": False},
            )
        except: pass
        try:
            self.db["chats"].create_index(
                [
                    ("type", ASCENDING),
                    ("members", ASCENDING),
                    ("deleted", ASCENDING),
                    ("last_active", DESCENDING),
                ],
                name="user_chats",
            )
        except: pass

        # Create reserved accounts
        for username in ["Server", "Deleted", "Meower", "Admin", "username"]:
            try:
                self.db.usersv0.insert_one({
                    "_id": username,
                    "lower_username": username.lower(),
                    "uuid": username,
                    "created": int(time.time()),
                    "pfp_data": None,
                    "quote": None,
                    "pswd": None,
                    "tokens": None,
                    "permissions": None,
                    "ban": None,
                    "last_seen": None,
                    "delete_after": None
                })
            except: pass

        # Create status file
        try:
            self.db.config.insert_one({
                "_id": "status",
                "repair_mode": False,
                "registration": False
            })
        except: pass

        # Create Filter file
        try:
            self.db.config.insert_one({
                "_id": "filter",
                "whitelist": [],
                "blacklist": []
            })
        except: pass

        # Migrations
        server_user = self.db.usersv0.find_one({"_id": "Server"})
        if "banned" in server_user:  # moderation update
            self.log(
                "Running migration for moderation update...\n\nPlease do not kill the server!"
            )

            self.log("Updating user admin permissions...")
            level1 = (
                Permissions.VIEW_REPORTS
                | Permissions.EDIT_REPORTS
                | Permissions.VIEW_NOTES
                | Permissions.EDIT_NOTES
                | Permissions.VIEW_POSTS
                | Permissions.EDIT_POSTS
                | Permissions.VIEW_INBOXES
                | Permissions.CLEAR_USER_QUOTES
                | Permissions.SEND_ALERTS
                | Permissions.KICK_USERS
                | Permissions.VIEW_BAN_STATES
                | Permissions.EDIT_BAN_STATES
            )
            level2 = (
                level1
                | Permissions.VIEW_ALTS
                | Permissions.CLEAR_USER_POSTS
            )
            level3 = (
                level2
                | Permissions.DELETE_USERS
                | Permissions.VIEW_IPS
                | Permissions.BLOCK_IPS
                | Permissions.VIEW_CHATS
                | Permissions.EDIT_CHATS
                | Permissions.SEND_ANNOUNCEMENTS
                | Permissions.VIEW_AUDIT_LOG
            )
            self.db.usersv0.update_many({"lvl": 0}, {"$set": {"permissions": 0}})
            self.db.usersv0.update_many({"lvl": 1}, {"$set": {"permissions": level1}})
            self.db.usersv0.update_many({"lvl": 2}, {"$set": {"permissions": level2}})
            self.db.usersv0.update_many({"lvl": 3}, {"$set": {"permissions": level3}})
            self.db.usersv0.update_many(
                {"lvl": 4}, {"$set": {"permissions": Permissions.SYSADMIN}}
            )

            self.log("Updating user ban statuses...")
            self.db.usersv0.update_many(
                {"banned": False},
                {"$set": {"ban": {"state": "None", "expires": 0, "reason": ""}}},
            )
            self.db.usersv0.update_many(
                {"banned": True},
                {"$set": {"ban": {"state": "PermBan", "expires": 0, "reason": ""}}},
            )

            self.log("Updating users...")
            self.db.usersv0.update_many(
                {}, {"$set": {"last_seen": None}, "$unset": {"lvl": "", "banned": ""}}
            )

            self.log("Updating netlogs...")
            ip_banlist = self.db.config.find_one({"_id": "IPBanlist"})
            self.db.netlog.update_many({}, {"$set": {"last_used": int(time.time())}})
            self.db.netlog.update_many(
                {"_id": {"$in": ip_banlist["index"]}}, {"$set": {"banned": True}}
            )
            self.db.netlog.update_many(
                {"_id": {"$nin": ip_banlist["index"]}}, {"$set": {"banned": False}}
            )
            self.db.config.delete_one({"_id": "IPBanlist"})

            self.log("Updating chats...")
            self.db.chats.update_many(
                {},
                {
                    "$set": {
                        "created": int(time.time()),
                        "last_active": int(time.time()),
                        "deleted": False,
                    }
                },
            )

            self.log("Updating posts...")
            self.db.posts.update_many(
                {"isDeleted": True}, {"$set": {"deleted_at": int(time.time())}}
            )

            self.log("Migration completed!")

        self.log("Files initialized!")

    def get_total_pages(self, collection, query):
        item_count = self.db[collection].count_documents(query)
        if (item_count % 25) == 0:
            if (item_count < 25):
                return 1
            else:
                return (item_count // 25)
        else:
            return (item_count // 25)+1

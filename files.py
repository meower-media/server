from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
import time
from uuid import uuid4
import os
from dotenv import load_dotenv
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

        mongo_uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
        self.log(
            "Connecting to database...\n(If it seems like the server is stuck or the server randomly crashes, it probably means it couldn't connect to the database)"
        )
        self.db = MongoClient(mongo_uri)["meowerserver"]

        # Check connection status
        if self.db.client.get_database("meowerserver") == None:
            self.log("Failed to connect to MongoDB database!")
        else:
            self.log("Connected to database")

        # Create database collections
        for item in {
            "config",
            "usersv0",
            "netlog",
            "posts",
            "chats",
            "reports",
            "admin_notes",
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
        except:
            pass
        try:
            self.db["netlog"].create_index([("users", ASCENDING)], name="users")
        except:
            pass
        try:
            self.db["netlog"].create_index(
                [("last_active", ASCENDING)],
                name="last_active_ttl",
                expireAfterSeconds=7776000,
                partialFilterExpression={"banned": False},
            )
        except:
            pass
        try:
            self.db["netlog"].create_index(
                [("banned", ASCENDING)],
                name="banned",
                partialFilterExpression={"banned": True},
            )
        except:
            pass
        try:
            self.db["posts"].create_index(
                [
                    ("post_origin", ASCENDING),
                    ("isDeleted", ASCENDING),
                    ("t.e", DESCENDING),
                    ("u", ASCENDING),
                ],
                name="default",
                partialFilterExpression={"isDeleted": False},
            )
        except:
            pass
        try:
            self.db["posts"].create_index(
                [
                    ("post_origin", ASCENDING),
                    ("isDeleted", ASCENDING),
                    ("p", TEXT),
                    ("t.e", DESCENDING),
                ],
                name="content_search",
                partialFilterExpression={"post_origin": "home", "isDeleted": False},
            )
        except:
            pass
        try:
            self.db["posts"].create_index(
                [
                    ("u", ASCENDING),
                    ("post_origin", ASCENDING),
                    ("isDeleted", ASCENDING),
                    ("t.e", DESCENDING),
                ],
                name="user_search",
            )
        except:
            pass
        try:
            self.db["posts"].create_index(
                [("deleted_at", ASCENDING)],
                name="deleted_at_ttl",
                expireAfterSeconds=2592000,
                partialFilterExpression={"isDeleted": True, "mod_deleted": False},
            )
        except:
            pass
        try:
            self.db["chats"].create_index(
                [
                    ("members", ASCENDING),
                    ("deleted", ASCENDING),
                    ("last_active", DESCENDING),
                ],
                name="user_chats",
            )
        except:
            pass

        # Create reserved accounts
        for username in ["Server", "Deleted", "Meower", "Admin", "username"]:
            self.create_item(
                "usersv0",
                username,
                {
                    "lower_username": username.lower(),
                    "created": int(time.time()),
                    "uuid": str(uuid4()),
                    "unread_inbox": False,
                    "theme": "",
                    "mode": None,
                    "sfx": None,
                    "debug": None,
                    "bgm": None,
                    "bgm_song": None,
                    "layout": None,
                    "pfp_data": None,
                    "quote": None,
                    "email": None,
                    "pswd": None,
                    "tokens": [],
                    "permissions": 0,
                    "ban": {"state": "None", "expires": 0, "reason": ""},
                    "last_ip": None,
                    "last_seen": None,
                },
            )

        # Create status file
        self.create_item(
            "config", "status", {"repair_mode": False, "is_deprecated": False}
        )

        # Create Filter file
        self.create_item("config", "filter", {"whitelist": [], "blacklist": []})

        # Migrations
        server = self.db.usersv0.find_one({"_id": "Server"})
        if "banned" in server:  # big moderation update
            self.log(
                "Running migration for big moderation update...\n\nPlease do not kill the server!"
            )

            self.log("Updating user admin permissions...")
            level1 = (
                Permissions.DELETE_POSTS
                | Permissions.VIEW_INBOXES
                | Permissions.CLEAR_USER_QUOTES
                | Permissions.SEND_ALERTS
                | Permissions.KICK_USERS
                | Permissions.VIEW_BAN_STATES
                | Permissions.EDIT_BAN_STATES
                | Permissions.VIEW_NOTES
                | Permissions.EDIT_NOTES
            )
            level2 = level1 | Permissions.VIEW_ALTS | Permissions.CLEAR_USER_POSTS
            level3 = (
                level2
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

    def does_item_exist(self, collection, id):
        if self.db[collection].count_documents({"_id": id}) > 0:
            return True
        else:
            return False

    def create_item(self, collection, id, data):
        if collection in self.db.list_collection_names():
            if not self.does_item_exist(collection, id):
                data["_id"] = id
                self.db[collection].insert_one(data)
                return True
            else:
                self.log("{0} already exists in {1}".format(id, collection))
                return False
        else:
            self.log("{0} collection doesn't exist".format(collection))
            return False

    def update_item(self, collection, id, data, upsert: bool = False):
        if upsert or self.does_item_exist(collection, id):
            self.db[collection].update_one({"_id": id}, {"$set": data}, upsert=upsert)
            return True
        else:
            return False

    def write_item(self, collection, id, data):
        if self.does_item_exist(collection, id):
            data["_id"] = id
            self.db[collection].find_one_and_replace({"_id": id}, data)
            return True
        else:
            return False

    def load_item(self, collection, id):
        item = self.db[collection].find_one({"_id": id})
        if item:
            return True, item
        else:
            return False, None

    def find_items(self, collection, query):
        return [
            item["_id"]
            for item in self.db[collection].find(query, projection={"_id": 1})
        ]

    def count_items(self, collection, query):
        return self.db[collection].count_documents(query)

    def delete_item(self, collection, id):
        if self.does_item_exist(collection, id):
            self.db[collection].delete_one({"_id": id})
            return True
        else:
            return False

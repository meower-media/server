from dotenv import load_dotenv
import pymongo
import radix
import time
import os

from security import DEFAULT_USER_SETTINGS, UserFlags, Permissions

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
            self.db = pymongo.MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"))[os.getenv("MONGO_DB", "meowerserver")]
            self.db.command("ping")
        except Exception as e:
            self.log(f"Failed connecting to database: {e}")
            exit()
        else:
            self.log("Connected to database!")


        # Moderation update migration
        if "config" in self.db.list_collection_names() and self.db.config.count_documents({"_id": "migration"}, limit=1) == 0:
            self.log(
                "Running migration for moderation update...\n\nPlease do not kill the server!"
            )

            LEGACY_LEVELS = {
                1: (
                    Permissions.VIEW_REPORTS
                    | Permissions.EDIT_REPORTS
                    | Permissions.VIEW_NOTES
                    | Permissions.EDIT_NOTES
                    | Permissions.VIEW_POSTS
                    | Permissions.DELETE_POSTS
                    | Permissions.SEND_ALERTS
                    | Permissions.KICK_USERS
                    | Permissions.CLEAR_USER_QUOTES
                    | Permissions.VIEW_BAN_STATES
                    | Permissions.EDIT_BAN_STATES
                ),
                2: Permissions.VIEW_ALTS,
                3: (
                    Permissions.DELETE_USERS
                    | Permissions.VIEW_IPS
                    | Permissions.BLOCK_IPS
                    | Permissions.VIEW_CHATS
                    | Permissions.EDIT_CHATS
                    | Permissions.SEND_ANNOUNCEMENTS
                )
            }

            self.log("Updating users...")
            all_usernames = []
            unique_usernames = set([
                "server",
                "deleted",
                "meower",
                "admin",
                "username"
            ])
            user_updates = []
            user_settings_inserts = []
            for user in self.db.usersv0.find({}):
                # Delete user if it has a duplicate username
                if user["lower_username"] in unique_usernames:
                    user_updates.append(pymongo.DeleteOne({"_id": user["_id"]}))
                    continue

                # Migrate settings to user_settings collection
                user_settings = {"_id": user["_id"]}
                for key, default in DEFAULT_USER_SETTINGS.items():
                    value = user.pop(key, default)
                    if isinstance(value, type(default)):
                        user_settings[key] = value
                    else:
                        user_settings[key] = default
                user_settings_inserts.append(pymongo.InsertOne(user_settings))

                # Apply new permissions
                legacy_level = user.get("lvl", 0)
                if legacy_level == 4:
                    user["permissions"] = Permissions.SYSADMIN
                elif legacy_level == 3:
                    user["permissions"] = (LEGACY_LEVELS[1] | LEGACY_LEVELS[2] | LEGACY_LEVELS[3])
                elif legacy_level == 2:
                    user["permissions"] = (LEGACY_LEVELS[1] | LEGACY_LEVELS[2])
                elif legacy_level == 1:
                    user["permissions"] = LEGACY_LEVELS[1]

                # Apply new ban state
                if user.get("banned"):
                    user["ban"] = {
                        "state": "perm_ban",
                        "restrictions": 0,
                        "expires": 0,
                        "reason": ""
                    }

                # Validate other keys on user
                expected_keys = {
                    "_id": None,
                    "lower_username": None,
                    "uuid": None,
                    "created": int(time.time()),
                    "pfp_data": 1,
                    "quote": "",
                    "pswd": None,
                    "tokens": [],
                    "flags": 0,
                    "permissions": 0,
                    "ban": {
                        "state": "none",
                        "restrictions": 0,
                        "expires": 0,
                        "reason": ""
                    },
                    "last_seen": None,
                    "delete_after": None
                }
                for key in list(user.keys()):
                    if key not in expected_keys:
                        del user[key]
                for key, default in expected_keys.items():
                    if key not in user:
                        user[key] = default

                user_updates.append(pymongo.ReplaceOne({"_id": user["_id"]}, user))
                all_usernames.append(user["_id"])
                unique_usernames.add(user["lower_username"])
            self.db.user_settings.bulk_write(user_settings_inserts)
            self.db.usersv0.drop_indexes()
            self.db.usersv0.bulk_write(user_updates)

            self.log("Updating chats...")
            self.db.chats.bulk_write([
                pymongo.UpdateMany({}, {"$pull": {"members": {"$nin": all_usernames}}}),
                pymongo.DeleteMany({"members": {"$size": 0}}),
                pymongo.UpdateMany({}, {"$set": {
                    "type": 0,
                    "created": int(time.time()),
                    "last_active": int(time.time()),
                    "deleted": False
                }})
            ])
            self.db.chats.drop_indexes()
            all_chat_ids = [chat["_id"] for chat in self.db.chats.find({}, projection={"_id": 1})]

            self.log("Updating posts...")
            self.db.posts.bulk_write([
                pymongo.DeleteMany({"$or": [
                    {"u": {"$nin": ["Server"] + all_usernames}},
                    {"post_origin": {"$nin": ["home", "inbox"] + all_chat_ids}}
                ]}),
                pymongo.UpdateMany({"isDeleted": True}, [{"$set": {"deleted_at": "$t.e"}}])
            ])
            self.db.posts.drop_indexes()

            self.log("Migrating IP blocks...")
            ip_banlist = self.db.config.find_one({"_id": "IPBanlist"})
            if ip_banlist:
                _radix = radix.Radix()
                netblocks = []
                for ip in ip_banlist.get("wildcard", []):
                    try:
                        radix_node = _radix.add(ip)
                        netblocks.append(pymongo.InsertOne({
                            "_id": radix_node.prefix,
                            "type": 0,
                            "created": int(time.time())
                        }))
                    except: pass
                self.db.netblock.bulk_write(netblocks)

            self.log("Dropping unnecessary data...")
            self.db.config.delete_many({"_id": {"$ne": "filter"}})
            self.db.netlog.drop()
            self.db.reports.drop()

            self.log("Done! It may take a bit to rebuild the indexes...")


        # Create database collections
        for item in {
            "config",
            "usersv0",
            "user_settings",
            "relationships",
            "netinfo",
            "netlog",
            "netblock",
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

        # Users
        try:
            self.db.usersv0.create_index([("lower_username", pymongo.ASCENDING)], name="lower_username", unique=True)
        except: pass
        try:
            self.db.usersv0.create_index([
                ("lower_username", pymongo.TEXT),
                ("uuid", pymongo.TEXT),
                ("quote", pymongo.TEXT)
            ], name="search", partialFilterExpression={"pswd": {"$type": "string"}})
        except: pass
        try:
            self.db.usersv0.create_index([("created", pymongo.DESCENDING)], name="recent_users")
        except: pass
        try:
            self.db.usersv0.create_index([
                ("delete_after", pymongo.ASCENDING)
            ], name="scheduled_deletions", partialFilterExpression={"delete_after": {"$type": "number"}})
        except: pass

        # Relationships
        try:
            self.db.relationships.create_index([("_id.from", pymongo.ASCENDING)], name="from")
        except: pass

        # Netinfo
        try:
            self.db.netinfo.create_index([("last_refreshed", pymongo.ASCENDING)], name="last_refreshed")
        except: pass

        # Netlog
        try:
            self.db.netlog.create_index([("_id.ip", pymongo.ASCENDING)], name="ip")
        except: pass
        try:
            self.db.netlog.create_index([("_id.user", pymongo.ASCENDING)], name="user")
        except: pass
        try:
            self.db.netlog.create_index([("last_used", pymongo.ASCENDING)], name="last_used")
        except: pass

        # Posts
        try:
            self.db.posts.create_index(
                [
                    ("post_origin", pymongo.ASCENDING),
                    ("isDeleted", pymongo.ASCENDING),
                    ("t.e", pymongo.DESCENDING),
                    ("u", pymongo.ASCENDING),
                ],
                name="default"
            )
        except: pass
        try:
            self.db.posts.create_index(
                [("u", pymongo.ASCENDING)],
                name="user"
            )
        except: pass
        try:
            self.db.posts.create_index(
                [("p", pymongo.TEXT)],
                name="search",
                partialFilterExpression={"post_origin": "home", "isDeleted": False},
            )
        except: pass
        try:
            self.db.posts.create_index(
                [("deleted_at", pymongo.ASCENDING)],
                name="scheduled_purges",
                partialFilterExpression={"isDeleted": True, "mod_deleted": False},
            )
        except: pass

        # Post revisions
        try:
            self.db.post_revisions.create_index(
                [("post_id", pymongo.ASCENDING), ("time", pymongo.DESCENDING)],
                name="post_revisions"
            )
        except: pass
        try:
            self.db.post_revisions.create_index(
                [("time", pymongo.ASCENDING)],
                name="scheduled_purges"
            )
        except: pass

        # Chats
        try:
            self.db.chats.create_index(
                [
                    ("members", pymongo.ASCENDING),
                    ("type", pymongo.ASCENDING)
                ],
                name="user_chats"
            )
        except: pass

        # Reports
        try:
            self.db.reports.create_index(
                [("content_id", pymongo.ASCENDING)],
                name="pending_reports",
                partialFilterExpression={"status": "pending"},
            )
        except: pass
        try:
            self.db.reports.create_index(
                [
                    ("escalated", pymongo.DESCENDING),
                    ("time", pymongo.DESCENDING),
                    ("status", pymongo.ASCENDING),
                    ("type", pymongo.ASCENDING)
                ],
                name="all_reports"
            )
        except: pass

        # Audit logs
        try:
            self.db.audit_log.create_index(
                [
                    ("time", pymongo.ASCENDING),
                    ("type", pymongo.ASCENDING)
                ],
                name="scheduled_purges"
            )
        except: pass


        # Create reserved accounts
        for username in ["Server", "Deleted", "Meower", "Admin", "username"]:
            try:
                self.db.usersv0.insert_one({
                    "_id": username,
                    "lower_username": username.lower(),
                    "uuid": None,
                    "created": None,
                    "pfp_data": None,
                    "quote": None,
                    "pswd": None,
                    "tokens": None,
                    "flags": UserFlags.SYSTEM,
                    "permissions": None,
                    "ban": None,
                    "last_seen": None,
                    "delete_after": None
                })
            except: pass


        # Create migration item
        try:
            self.db.config.insert_one({
                "_id": "migration",
                "database": 1
            })
        except: pass

        # Create status item
        try:
            self.db.config.insert_one({
                "_id": "status",
                "repair_mode": False,
                "registration": False
            })
        except: pass

        # Create filter item
        try:
            self.db.config.insert_one({
                "_id": "filter",
                "whitelist": [],
                "blacklist": []
            })
        except: pass


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

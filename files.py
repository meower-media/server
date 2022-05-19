from pymongo import MongoClient

"""

Meower Files Module

This module provides filesystem functionality and a primitive JSON-file based database interface.
This file should be modified/refactored to interact with a JSON-friendly database server instead of filesystem directories and files.

"""

class Files:
    def __init__(self, logger, errorhandler):
        self.log = logger
        self.errorhandler = errorhandler

        mongo_ip = "mongodb://localhost:27017"
        self.log("Connecting to database '{0}'\n(If it seems like the server is stuck, it probably means it couldn't connect to the database)".format(mongo_ip))
        self.db = MongoClient(mongo_ip)["meowerserver"]

        # Check connection status
        if self.db.client.get_database("meowerserver") == None:
            self.log("Failed to connect to MongoDB database!")
        else:
            self.log("Connected to database")

        # Create database collections
        for item in ["config", "usersv0", "usersv1", "netlog", "posts", "chats"]:
            if not item in self.db.list_collection_names():
                self.log("Creating collection {0}".format(item))
                self.db.create_collection(name=item)
        
        # Create collection indexes
        self.db["netlog"].create_index("users")
        self.db["usersv0"].create_index("lower_username")
        self.db["posts"].create_index("u")
        self.db["posts"].create_index("post_origin")
        self.db["posts"].create_index("type")
        self.db["chats"].create_index("members")
        
        # Create reserved accounts
        self.create_item("usersv0", "Server", {
            "lower_username": "server",
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
            "lvl": None,
            "banned": False
        })
        
        self.create_item("usersv0", "Deleted", {
            "lower_username": "deleted",
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
            "lvl": None,
            "banned": False
        })

        self.create_item("usersv0", "username", {
            "lower_username": "username",
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
            "lvl": None,
            "banned": False
        })

        self.create_item("usersv0", "Meower", {
            "lower_username": "meower",
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
            "lvl": None,
            "banned": False
        })

        # Create IP banlist file
        self.create_item("config", "IPBanlist", {
            "wildcard": [
                "127.0.0.1",
            ],
            "users": {
                "Deleted": "127.0.0.1",
                "Server": "127.0.0.1",
            }
        })
        
        # Create Version support file
        self.create_item("config", "supported_versions", {
            "index": [
                "scratch-beta-5-r6",
            ]
        })
        
        # Create Trust Keys file
        self.create_item("config", "trust_keys", {
            "index": [
                "meower",
            ]
        })

        # Create Filter file
        self.create_item("config", "filter", {
            "whitelist": [], 
            "blacklist": []
        })

        # Create status file
        self.create_item("config", "status", {
            "repair_mode": False,
            "is_deprecated": False
        })
        
        self.db["usersv0"].update_many({"last_login": None}, {"$set": {"last_login": None}})
        self.db["usersv0"].update_many({"created_at": None}, {"$set": {"created_at": 1668465928}})
        self.db["usersv0"].update_many({}, {"$set": {"layout": "new"}})
        self.db["usersv0"].update_many({"flags": None}, {"$set": {"flags": {"dormant": False, "locked_until": 0, "suspended_until": 0, "banned_until": 0, "delete_after": None, "isDeleted": False}}})
        self.db["usersv0"].update_many({"banned": True}, {"$set": {"flags": {"banned_until": -1}}})
        self.db["usersv0"].update_many({"isDeleted": True}, {"$set": {"flags": {"isDeleted": True}}})

        self.log("Files initialized!")

    def does_item_exist(self, collection, id):
        if collection in self.db.list_collection_names():
            if self.db[collection].find_one({"_id": id}) != None:
                return True
            else:
                return False
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

    def update_item(self, collection, id, data):
        if collection in self.db.list_collection_names():
            if self.does_item_exist(collection, id):
                self.db[collection].update_one({"_id": id}, {"$set": data})
                return True
            else:
                return False
        else:
            return False

    def write_item(self, collection, id, data):
        if collection in self.db.list_collection_names():
            if self.does_item_exist(collection, id):
                data["_id"] = id
                self.db[collection].find_one_and_replace({"_id": id}, data)
                return True
            else:
                return False
        else:
            return False

    def load_item(self, collection, id):
        if collection in self.db.list_collection_names():
            if self.does_item_exist(collection, id):
                return True, self.db[collection].find_one({"_id": id})
            else:
                return False, None
        else:
            return False, None

    def find_items(self, collection, query, sort_by_epoch=False):
        if collection in self.db.list_collection_names():
            payload = []
            if sort_by_epoch:
                tmp = {}
            for item in self.db[collection].find(query):
                print(item)
                if sort_by_epoch:
                    if "t" in item:
                        if "e" in item["t"]:
                            tmp[item["_id"]] = item["t"]["e"]
                else:
                    payload.append(item["_id"])
            if sort_by_epoch:
                tmp = sorted(tmp.items(), key=lambda x: x[1])
                for i in tmp:
                    payload.append(str(i[0]))
            return payload
        else:
            return []

    def delete_item(self, collection, id):
        if collection in self.db.list_collection_names():
            if self.does_item_exist(collection, id):
                self.db[collection].delete_one({"_id": id})
                return True
            else:
                return False
        else:
            return False
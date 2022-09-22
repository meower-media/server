import pymongo

class Database:
    
    """
    Meower Database - Port complete
    
    This is a shared class that acts as an interface to the Meower's MongoDB
    server.
    """
    
    def __init__(self, parent, db_ip, timeout_ms:int = 10000):
        # Inherit parent class attributes
        self.parent = parent
        self.log = parent.log
        self.uuid = parent.uuid
        self.time = parent.time
        self.full_stack = parent.cl.supporter.full_stack
        
        # Initialize database connection
        self.log(f"Connecting to the MongoDB server...")
        self.dbclient = pymongo.MongoClient(db_ip, serverSelectionTimeoutMS = timeout_ms)
        try:
            self.dbclient.server_info() # Attempt to get info from the server, pymongo will raise an exception and exit if it fails
        except pymongo.errors.ServerSelectionTimeoutError:
            self.log("Failed to connect the MongoDB server.")
            exit()
        
        # Create database collections
        self.log("Connected to the MongoDB server!")
        
        self.dbclient = self.dbclient["meowerserver"]
        self.log("Meower mongodb interface initializing...")
        
        # Create collections
        for item in ["config", "usersv0", "usersv1", "netlog", "posts", "chats", "reports"]:
            if not item in self.dbclient.list_collection_names():
                self.log("Creating collection {0}".format(item))
                self.dbclient.create_collection(name=item)
        
        # Create collection indexes
        self.dbclient["netlog"].create_index("users")
        self.dbclient["usersv0"].create_index("lower_username")
        self.dbclient["posts"].create_index("u")
        self.dbclient["posts"].create_index("post_origin")
        self.dbclient["posts"].create_index("type")
        self.dbclient["posts"].create_index("p")
        self.dbclient["chats"].create_index("members")
    
        # Create reserved accounts
        for username in ["Server", "Deleted", "Meower", "Admin", "username", "Annoucement", "Alert"]:
            self.create_item("usersv0", username, {
                "lower_username": username.lower(),
                "created": int(self.time()),
                "uuid": str(self.uuid.uuid4()),
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
                "lvl": None,
                "banned": False,
                "last_ip": None
            })
        
        # Create IP banlist file
        self.create_item("config", "IPBanlist", {
            "wildcard": [],
            "users": {}
        })
        
        # Create Version support file
        self.create_item("config", "supported_versions", {
            "index": [
                "scratch-beta-5-r7",
                "scratch-beta-6"
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
            "panic_mode": False,
            "is_deprecated": False
        })

        self.log("Meower mongodb interface initialized!")
        
    def does_item_exist(self, collection, id):
        if collection in self.dbclient.list_collection_names():
            if self.dbclient[collection].find_one({"_id": id}) != None:
                return True
            else:
                return False
        else:
            return False
             
    def create_item(self, collection, id, data):
        if collection in self.dbclient.list_collection_names():
            if not self.does_item_exist(collection, id):
                data["_id"] = id
                self.dbclient[collection].insert_one(data)
                return True
            else:
                self.log("{0} already exists in {1}".format(id, collection))
                return False
        else:
            self.log("{0} collection doesn't exist".format(collection))
            return False

    def update_item(self, collection, id, data):
        if collection in self.dbclient.list_collection_names():
            if self.does_item_exist(collection, id):
                self.dbclient[collection].update_one({"_id": id}, {"$set": data})
                return True
            else:
                return False
        else:
            return False

    def write_item(self, collection, id, data):
        if collection in self.dbclient.list_collection_names():
            if self.does_item_exist(collection, id):
                data["_id"] = id
                self.dbclient[collection].find_one_and_replace({"_id": id}, data)
                return True
            else:
                return False
        else:
            return False

    def load_item(self, collection, id):
        if collection in self.dbclient.list_collection_names():
            if self.does_item_exist(collection, id):
                return True, self.dbclient[collection].find_one({"_id": id})
            else:
                return False, None
        else:
            return False, None

    def find_items(self, collection, query):
        if collection in self.dbclient.list_collection_names():
            payload = []
            for item in self.dbclient[collection].find(query):
                payload.append(item["_id"])
            return payload
        else:
            return []

    def count_items(self, collection, query):
        if collection in self.dbclient.list_collection_names():
            return self.dbclient[collection].count_documents(query)
        else:
            return 0

    def delete_item(self, collection, id):
        if collection in self.dbclient.list_collection_names():
            if self.does_item_exist(collection, id):
                self.dbclient[collection].delete_one({"_id": id})
                return True
            else:
                return False
        else:
            return False
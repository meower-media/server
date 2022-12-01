import pymongo

class database:
    
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
        self.cloudlink = parent.server
        self.pymongo = pymongo
        
        # Initialize database connection
        self.log(f"[Database] Connecting to the MongoDB server...")
        self.dbclient = self.pymongo.MongoClient(db_ip, serverSelectionTimeoutMS = timeout_ms)
        try:
            self.dbclient.server_info() # Attempt to get info from the server, pymongo will raise an exception and exit if it fails
        except pymongo.errors.ServerSelectionTimeoutError:
            self.log("[Database] Failed to connect the MongoDB server.")
            exit()
        
        # Create database collections
        self.log("[Database] Connected to the MongoDB server!")
        self.dbclient = self.dbclient["meowerbeta"]
        
        # Create collections
        for item in ["config", "usersv0", "usersv1", "netlog", "posts", "chats", "reports"]:
            if not item in self.dbclient.list_collection_names():
                self.log("[Database] Creating collection {0}".format(item))
                self.dbclient.create_collection(name=item)
        
        # Create collection indexes
        self.dbclient["netlog"].create_index("users")
        self.dbclient["usersv0"].create_index("lower_username")
        for index in ["u", "post_origin", "p"]:
            self.dbclient["posts"].create_index(index)
        self.dbclient["chats"].create_index("members")
        
        # Create reserved accounts
        for username in ["Server", "Deleted", "Meower"]:
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
                "token_vers": None,
                "lvl": None,
                "banned": False,
                "last_ip": None
            }, silent = True)
        
        # Create IP banlist file
        self.create_item("config", "IPBanlist", {
            "wildcard": [],
            "users": {}
        }, silent = True)
        
        # Create Version support file
        self.create_item("config", "supported_versions", {
            "index": [
                "scratch-beta-5-r7",
                "scratch-beta-5-r8",
                "scratch-beta-6",
                "0.6.0"
            ]
        }, silent = True)

        # Create Filter file
        self.create_item("config", "filter", {
            "usernames": ["Admin", "username", "Annoucement", "Alert"],
            "whitelist": [], 
            "blacklist": []
        }, silent = True)

        # Create status file
        self.create_item("config", "status", {
            "repair_mode": False,
            "is_deprecated": False
        }, silent = True)
        
        # Load the IP Blocklist
        self.log("[Database] Loading IP blocklist...")
        result, data = self.load_item("config", "IPBanlist")
        if not result:
            self.log("[Database] IP blocklist failed to load!")
        else:
            tmp_blacklist = list()
            for bad in data["wildcard"]:
                tmp_blacklist.append(bad)
            
            self.log(f"[Database] Loaded IP blocklist, storing {len(tmp_blacklist)} blocked addresses.")
            self.cloudlink.ip_blocklist = tmp_blacklist
        
        # Load wordfilters
        self.log("[Database] Loading wordfilter data...")
        result, data = self.load_item("config", "filter")
        if not result:
            self.log("[Database] Wordfilter data failed to load!")
        else:
            tmp_whitelist = list()
            for good in data["whitelist"]:
                tmp_whitelist.append(good)
            
            tmp_blacklist = list()
            for bad in data["blacklist"]:
                tmp_blacklist.append(bad)
            
            # Create the filter if it is blank
            if self.parent.supporter.filter == None:
                self.parent.supporter.filter = dict()
            
            self.log(f"[Database] Loaded wordfilter data, storing {len(tmp_whitelist)} allowed phrases and {len(tmp_blacklist)} blocked phrases.")
            self.parent.supporter.filter["whitelist"] = tmp_whitelist
            self.parent.supporter.filter["blacklist"] = tmp_blacklist
        
        self.log("[Database] Meower database initialized!")
    
    def get_index(self, location="posts", query={"post_origin": "home", "isDeleted": False},  truncate=False, page=1, sort="t.e"):
        if truncate:
            all_items = self.dbclient[location].find(query).sort("t.e", self.pymongo.DESCENDING).skip((page-1)*25).limit(25)
        else:
            all_items = self.dbclient[location].find(query)
        
        item_count = self.dbclient[location].count_documents(query)
        if item_count == 0:
            pages = 0
        else:
            if (item_count % 25) == 0:
                if (item_count < 25):
                    pages = 1
                else:
                    pages = (item_count // 25)
            else:
                pages = (item_count // 25)+1

        query_get = []
        for item in all_items:
            query_get.append(item)
        
        query_return = {
            "query": query,
            "index": query_get,
            "page#": page,
            "pages": pages
        }
        
        return query_return
    
    def does_item_exist(self, collection, id):        
        # Return if an entry exists for that document query
        return self.dbclient[collection].find_one({"_id": id}) != None
    
    def create_item(self, collection, id, data, silent = False):
        # Create document in the collection
        data["_id"] = id
        try:
            self.dbclient[collection].insert_one(data)
        except:
            return False
        else:
            return True
    
    def update_item(self, collection, id, data):
        # Check if the document exists within the collection
        if not self.does_item_exist(collection, id):
            self.log("[Database] Failed to update_item: {0} does not exist in {1}".format(id, collection))
            return False
        
        # Update the document
        self.dbclient[collection].update_one({"_id": id}, {"$set": data})
        return True

    def write_item(self, collection, id, data):
        # Check if the document exists within the collection
        if not self.does_item_exist(collection, id):
            self.log("[Database] Failed to write_item: {0} does not exist in {1}".format(id, collection))
            return False

        # Update the document
        data["_id"] = id
        self.dbclient[collection].find_one_and_replace({"_id": id}, data)
        return True
    
    def load_item(self, collection, id):
        # Get item from database
        item = self.dbclient[collection].find_one({"_id": id})
        
        # Return the document data
        return (item is not None), item
    
    def find_items(self, collection, query):        
        # Return all documents located in the collection for that query
        payload = []
        for item in self.dbclient[collection].find(query, projection = {"_id": 1}):
            payload.append(item["_id"])
        return payload
    
    def count_items(self, collection, query):
        # Return total count of all documents in the collection for that query
        return self.dbclient[collection].count_documents(query)

    def delete_item(self, collection, id):
        # Check if the document exists within the collection
        if not self.does_item_exist(collection, id):
            self.log("[Database] Failed to delete_item: {0} does not exist in {1}".format(id, collection))
            return False
        
        # Update the document
        self.dbclient[collection].delete_one({"_id": id})
        return True

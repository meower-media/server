from passlib.hash import bcrypt
import time
import jwt
import os

class accounts:
    
    """
    Meower Accounts - Port complete
    
    This class provides a friendly interface to manage accounts and provide authentication.
    """
    
    def __init__(self, parent):
        # Inherit parent class attributes
        self.parent = parent
        self.log = parent.log
        self.db = parent.db
        self.uuid = parent.uuid
        self.full_stack = parent.server.supporter.full_stack
        self.default_strength = 12
        
        # These keys should not be modified/read by a client unless explicitly requested
        self.protected_keys = [
            "lvl",
            "pswd",
            "banned",
            "email",
            "last_ip",
            "lower_username", 
            "uuid",
            "token_vers", 
            "created"
        ]
        
        self.all_user_keys = [
            "lower_username",
            "uuid",
            "unread_inbox",
            "theme",
            "mode",
            "sfx",
            "debug",
            "bgm",
            "bgm_song",
            "layout",
            "pfp_data",
            "quote",
            "email",
            "pswd",
            "token_vers",
            "lvl",
            "banned",
            "last_ip"
        ]
        
        # Codes
        self.accountExists = 1
        self.accountDoesNotExist = 2
        self.accountIOError = 3
        self.accountBanned = 4
        self.accountNotBanned = 5
        self.accountCreated = 6
        self.accountDeleted = 7
        self.accountUpdated = 8
        self.accountAuthenticated = 9
        self.accountNotAuthenticated = 10
        self.accountAuthenticatedWithToken = 11
        
    def create_account(self, username:str, password:str, strength:int = None):
        if strength == None:
            strength = self.default_strength
        
        # Datatype checks
        if (not type(username) == str) or (not type(password) == str) or (not type(strength) == int):
            raise TypeError
        
        # Check if the account exists
        if self.account_exists(username, True) == self.accountExists:
           self.log(f"[Accounts] Not creating account {username}: Account already exists")
           return self.accountExists
        
        self.log(f"[Accounts] Creating account: {username}")
        
        # Create account template (revise in Beta 6, use usersv1)
        account_data = {
            "_id": self.uuid.uuid4(),
            "username": username,
            "created": int(time.time()), # is this redundant?
            "unread_inbox": False,
            "theme": "orange",
            "mode": True,
            "sfx": True,
            "debug": False,
            "bgm": True,
            "bgm_song": 2,
            "layout": "new",
            "pfp_data": 1,
            "quote": "",
            "email": "",
            "pswd": bcrypt.hash(password, rounds = strength),
            "token_vers": str(self.uuid.uuid4()),
            "lvl": 0,
            "banned": 0,
            "last_ip": None
        }
        
        # Store new account in the database
        if self.db.create_item("usersv0", username, account_data):
            return self.accountCreated
        else:
            return self.accountIOError
    
    def delete_account(self, username:str):
        # Datatype checks
        if not isinstance(username, str):
            raise TypeError
        
        # Check if the account exists
        if self.account_exists(username, True) == self.accountDoesNotExist:
           self.log(f"[Accounts] Not deleting account {username}: Account does not exist")
           return self.accountDoesNotExist
        
        self.log(f"[Accounts] Deleting account: {username}")
        
        # Delete the user's data from the database
        self.db.delete_item("usersv0", username)
        
        # Delete all user's chats
        index = self.db.dbclient["chats"].find({"members": {"$all": [username]}})
        for chat in index:
            chat["members"].remove(username)
            if chat["owner"] == username:
                if len(chat["members"]) > 0:
                    chat["owner"] = chat["members"][0]
                else:
                    chat["owner"] = "Deleted"
            self.db.write_item("chats", chat["_id"], chat)
        
        # Delete all user posts
        self.db.dbclient["posts"].delete_many({"u": username})
        
        # Delete netlog data
        netlog_index = self.db.dbclient["netlog"].find({"users": {"$all": [username]}})
        for ip in netlog_index:
            ip["users"].remove(username)
            if len(ip["users"]) == 0:
                self.files.delete_item("netlog", ip["_id"])
            else:
                if ip["last_user"] == username:
                    ip["last_user"] = ip["users"][(len(ip["users"])-1)]
                self.db.write_item("netlog", ip["_id"], ip)
        
        return self.accountDeleted
    
    def authenticate_pswd(self, username:str, password:str):
        # Datatype checks
        if not (isinstance(username, str) and isinstance(password, str)):
            raise TypeError
        
        result, data = self.db.load_item("usersv0", username)
        # Prevent authentication if it failed to read the account
        if not result:
            self.log(f"[Accounts] Not authenticating account {username}: Account does not exist")
            return self.accountDoesNotExist

        # Prevent authentication if banned
        if (data["banned"] == -1) or (data["banned"] > int(time.time())):
            self.log(f"[Accounts] Not authenticating account {username}: Account banned")
            return self.accountBanned
        
        self.log(f"Authenticating account: {username}")
        
        # Check password
        if bcrypt.verify(password, data["pswd"]):
            return self.accountAuthenticated
        else:
            return self.accountNotAuthenticated
    
    def authenticate_token(self, username:str, token:str):
        # Datatype checks
        if not (isinstance(username, str) and isinstance(token, str)):
            raise TypeError
        
        # Prevent authentication if token has an invalid signature
        try:
            decoded_jwt = jwt.decode(token, os.environ["JWT_SECRET"], verify = True)
        except:
            return self.accountNotAuthenticated

        result, data = self.db.load_item("usersv0", username)
        # Prevent authentication if it failed to read the account
        if not result:
            self.log(f"[Accounts] Not authenticating account {username}: Account does not exist")
            return self.accountDoesNotExist

        # Prevent authentication if banned
        if (data["banned"] == -1) or (data["banned"] > int(time.time())):
            self.log(f"[Accounts] Not authenticating account {username}: Account banned")
            return self.accountBanned
        
        self.log(f"Authenticating account: {username}")
        
        # Check if the account has same version as token
        if (data["_id"] == decoded_jwt["u"]) and (data["token_vers"] == decoded_jwt["v"]):
            return self.accountAuthenticated
        else:
            return self.accountNotAuthenticated

    def create_token(self, username:str):
        # Datatype checks
        if not isinstance(username, str):
            raise TypeError

        result, data = self.db.load_item("usersv0", username)
        # Prevent authentication if it failed to read the account
        if not result:
            self.log(f"[Accounts] Not authenticating account {username}: Account does not exist")
            return self.accountDoesNotExist
        
        self.log(f"[Accounts] Creating token for account: {username}")
        
        # Create signed token
        token = jwt.encode({"id": str(self.uuid.uuid4()), "u": username, "v": data["token_vers"], "iat": int(time.time()), "exp": (int(time.time()) + 2592000)}, os.environ["JWT_SECRET"])
        
        self.log(f"[Accounts] Generated token: {token} for account: {username}")
        return token

    def change_password(self, username:str, newpassword:str, strength:int = None):
        if strength is None:
            strength = self.default_strength
        
        # Datatype checks
        if not (isinstance(username, str) and isinstance(newpassword, str) and isinstance(strength, int)):
            raise TypeError
        
        self.log(f"[Accounts] Updating account password: {username}")
        
        # Save new password hash and token vers
        result = self.db.update_item("usersv0", username, {"pswd": bcrypt.hash(newpassword, rounds = strength), "token_vers": str(self.uuid.uuid4())})

        if result:
            return self.accountUpdated
        else:
            return self.accountDoesNotExist
    
    def account_exists(self, username:str, ignore_case:bool = False):
        if not type(username) == str:
            raise TypeError
        
        if ignore_case:
            if self.db.does_item_exist("usersv0", username):
                return self.accountExists
            else:
                return self.accountDoesNotExist
        else:
            payload = self.db.count_items("usersv0", 
                {
                    "lower_username": username.lower()
                }
            )
            if len(payload) != 0:
                return self.accountDoesNotExist
            else:
                return self.accountExists
    
    def is_account_banned(self, username:str):
        # Datatype checks
        if not type(username) == str:
            raise TypeError
            
        # Check if the account exists
        if self.account_exists(username, True) == self.accountDoesNotExist:
           return self.accountDoesNotExist
        
        self.log(f"[Accounts] Reading account: {username}")
        
        result, data = self.db.load_item("usersv0", username)
        if not result:
            return self.accountIOError
        
        if data["banned"]:
            return self.accountBanned
        else:
            return self.accountNotBanned
    
    def update_setting(self, username:str, newdata:dict, forceUpdate:bool = False):
        # Datatype checks
        if (not type(username) == str) or (not type(newdata) == dict) or (not type(forceUpdate) == bool):
            raise TypeError
        
        # Load the account data
        result, account_data = self.db.load_item("usersv0", username)
        
        if not result:
            self.log(f"[Accounts] Not updating account data {username}: Account does not exist")
            return self.accountDoesNotExist
        
        for key, value in newdata.items():
            if key in self.all_user_keys:
                if forceUpdate:
                    account_data[key] = value
                else:
                    if key in self.protected_keys:
                        self.log(f"[Accounts] Blocking attempt to modify secure key {key}")
                    else:
                        # Prepare for stupidity
                        
                        typeCheck = type(key) == str
                        typeCheck = typeCheck and type(value) in [str, int, float, bool, dict]
                        typeCheck = typeCheck and not(self.parent.supporter.check_for_bad_chars_post(str(value)))
                        typeCheck = typeCheck and not len(str(value)) > 360
                        
                        if not typeCheck:
                            self.log(f"Key {key} failed type Check")
                            break
                        
                        if type(value) == str:
                            account_data[key] = self.parent.supporter.wordfilter(value)
                        else:
                            account_data[key] = value
            else:
                self.log(f"Not writing Key: {key} is unknown")
        
        result = self.db.write_item("usersv0", username, account_data)
        if not result:  
            return self.accountIOError
        else:
            return self.accountUpdated
    
    def get_account(self, username:str, omitSensitive:bool = False, isClient:bool = False):
        # Datatype checks
        if (not type(username) == str) or (not type(omitSensitive) == bool) or (not type(isClient) == bool):
            raise TypeError
        
        # Read the user from the database
        result, account_data = self.db.load_item("usersv0", str(username))
        if not result:
            self.log(f"[Accounts] Not getting account data {username}: Account does not exist")
            return self.accountDoesNotExist
       
        del account_data["_id"]
        del account_data["lower_username"]
        
        # Remove sensitive data
        if omitSensitive:
            for sensitive in [
                "_id",
                "lower_username",
                "unread_inbox",
                "theme",
                "mode",
                "sfx",
                "debug",
                "bgm",
                "bgm_song",
                "layout",
                "email",
                "pswd",
                "token_vers",
                "last_ip",
            ]:
                if sensitive in account_data:
                    del account_data[sensitive]
        if isClient:
            if "pswd" in account_data:
                del account_data["pswd"]
            if "email" in account_data:
                del account_data["email"]
            if "token_vers" in account_data:
                del account_data["token_vers"]
            if "last_ip" in account_data:
                del account_data["last_ip"]
        
        return account_data

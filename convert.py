from pymongo import MongoClient
import os
import json
from supporter import Supporter

db = MongoClient("mongodb://localhost:27017")["meowerserver"]
supporter = Supporter()

username_changes = {} # {"<username>": "<new username>"}
password_changes = {} # {"<username>": "<new password>"} -- Hashed passwords only
ban = []
unban = []
delete = []

if input("Welcome to the Meower server converter!\n\nType 'y' and press 'enter' to confirm you want to copy all data from the 'Meower' db folder to MongoDB.").lower() != "y":
    input("Aborted! Press 'enter' to exit.")
    exit()

print("Adding config data to Mongo...")
with open("Meower/Config/filter.json", 'r') as f:
    filter = json.loads(f.read())
db["config"].find_one_and_replace({"_id": "filter"}, filter)
print("Added filter to Mongo!")

with open("Meower/Config/supported_versions.json", 'r') as f:
    supported_versions = json.loads(f.read())
db["config"].find_one_and_replace({"_id": "supported_versions"}, supported_versions)
print("Added supported_versions to Mongo!")

with open("Meower/Config/trust_keys.json", 'r') as f:
    trust_keys = json.loads(f.read())
db["config"].find_one_and_replace({"_id": "trust_keys"}, trust_keys)
print("Added trust_keys to Mongo!")

with open("Meower/Jail/IPBanlist.json", 'r') as f:
    IPBanlist = json.loads(f.read())
db["config"].find_one_and_replace({"_id": "IPBanlist"}, IPBanlist)
print("Added IPBanlist to Mongo!")

print("Adding users to Mongo...")
for item in os.listdir("Meower/Userdata"):
    try:
        with open("Meower/Userdata/{0}".format(item), 'r') as f:
            userdata = json.loads(f.read())
        if item in username_changes:
            print("Changing username for {0} to {1}".format(item, username_changes[item]))
            userdata["_id"] = username_changes[item]
        else:
            userdata["_id"] = item
        if item in password_changes:
            print("Changing password for {0} to {1}".format(item, password_changes[item]))
            userdata["pswd"] = password_changes[item]
        if item in ban:
            print("Banning {0}".format(item))
            userdata["banned"] = True
        if item in unban:
            print("Unbanning {0}".format(item))
            userdata["banned"] = False
        userdata["lower_username"] = userdata["_id"].lower()
        userdata["last_ip"] = ""
        db["usersv0"].insert_one(userdata)
        print("Added {0} to Mongo!".format(userdata["_id"]))
    except Exception as e:
        print("Error: {0}".format(e))

print("Running integrity checks...")
failed = []
success = []
deleted = []
datatypes = {"theme": str, "mode": bool, "sfx": bool, "debug": bool, "bgm": bool, "bgm_song": int, "layout": str, "pfp_data": int, "quote": str, "email": str, "pswd": str, "lvl": int, "banned": bool, "last_ip": str}
default_values = {"theme": "orange", "mode": True, "sfx": True, "debug": False, "bgm": True, "bgm_song": 2, "layout": "new", "pfp_data": 1, "quote": "", "email": "", "last_ip": ""}
for item in os.listdir("Meower/Userdata"):
    userdata = db["usersv0"].find_one({"_id": item})
    if userdata == None:
        failed.append(item)
        print("Faile to move {0} to Mongo due to blank or severily corrupted userdata file!".format(item))
    else:
        if not item in ["Deleted", "Server", "username", "", "Meower"]:
            if item in delete:
                print("Deleted {0}".format(item))
                db["usersv0"].delete_one({"_id": item})
                deleted.append(item)
            for key in datatypes.keys():
                if type(userdata[key]) != datatypes[key]:
                    if key in default_values:
                        userdata[key] = default_values[key]
                        try:
                            db["usersv0"].find_one_and_replace({"_id": item}, userdata)
                            print("Restored {0} in {1} to default value due to minor integrity error!".format(key, item))
                        except:
                            failed.append(item)
                            print("Failed applying fix for {0} at {1}!".format(item, key))
                            db["usersv0"].delete_one({"_id": item})
                            break
                    else:
                        failed.append(item)
                        print("Failed integrity check for {0} at {1}!".format(item, key))
                        db["usersv0"].delete_one({"_id": item})
                        break
        if not item in failed:
            success.append(item)

print("\n\nConversion complete!\nSucceeded: {0}\nFailed: {1} : {2}\nDeleted: {3} : {4}".format(len(success), len(failed), failed, len(deleted), deleted))

input("Press 'enter' to exit.")
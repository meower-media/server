import pymongo
import string
from uuid import uuid4

permitted_chars_username = []
delete_these = []

def checkForBadCharsUsername(value):
    badchars = False
    for char in value:
        if not char in permitted_chars_username:
            badchars = True
            break
    return badchars

# Make permitted chars list
for char in string.ascii_letters:
    permitted_chars_username.append(char)
for char in string.digits:
    permitted_chars_username.append(char)
permitted_chars_username.extend(["_", "-"])

# Connect to DB
db = pymongo.MongoClient("mongodb://localhost:27017")["meowerserver"]
print("Connected to database!")

# Fix up my dumb spelling mistake
db["posts"].delete_many({"p": {"$regex": "Message a moderator"}})

# Update users
db["usersv0"].update_many({"unread_inbox": None}, {"$set": {"unread_inbox": True}})
db["usersv0"].update_many({"created": None}, {"$set": {"created": 1636929928}})
db["usersv0"].update_many({"tokens": None}, {"$set": {"tokens": []}})
db["usersv0"].update_many({"last_ip": None}, {"$set": {"last_ip": None}})
for user in db["usersv0"].find():
    if (len(user["_id"]) > 20) or (checkForBadCharsUsername(user["_id"])) or (len(user["_id"].strip()) == 0):
        delete_these.append(user["_id"])
    else:
        db["usersv0"].update_one({"_id": user["_id"]}, {"$set": {"lower_username": user["_id"].lower(), "uuid": str(uuid4())}})

# Delete bad accounts
if len(delete_these) > 0:
    print(delete_these)
    confirm = input("Delete {0} bad accounts? (y/n) ".format(len(delete_these)))
    if confirm == "y":
        for username in delete_these:
            db["posts"].delete_many({"u": username})
            chat_index = db["chats"].find({"members": {"$all": [username]}})
            for chat in chat_index:
                if chat["owner"] == username:
                    db["chats"].delete_one({"_id": chat["_id"]})
                else:
                    chat["members"].remove(username)
                    db["chats"].update_one({"_id": chat["_id"]}, {"$set": {"members": chat["members"]}})
            netlog_index = db["netlog"].find({"users": {"$all": [username]}})
            for ip in netlog_index:
                ip["users"].remove(username)
                if ip["last_user"] == username:
                    ip["last_user"] = "Deleted"
                db["netlog"].update_one({"_id": ip["_id"]}, {"$set": {"users": ip["users"], "last_user": ip["last_user"]}})
            db["usersv0"].delete_one({"_id": username})
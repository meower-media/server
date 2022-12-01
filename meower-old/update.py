from pymongo import MongoClient
from supporter import Supporter

supporter = Supporter()

db = MongoClient("mongodb://localhost:27017").meowerserver

for chat in db.chats.find({}):
    censored_name = supporter.wordfilter(chat["nickname"])
    if chat["nickname"] != censored_name:
        db.chats.update_one({"_id": chat["_id"]}, {"$set": {"nickname": censored_name}})

from pymongo import MongoClient
from datetime import datetime
import os
import ujson
import time
import secrets

from src.common.util import uid, logging, events


def migrate_from_v0(db):
    # Migrate users
    try:
        logging.info("Migrating users...")
        usernames = set()
        lower_usernames = set()
        for username in os.listdir("./Meower/Userdata"):
            try:
                f = open(f"./Meower/Userdata/{username}", "r")
                user = ujson.load(f)
                f.close()
                if username.lower() in lower_usernames:
                    raise Exception("Duplicate username")
                db.users.insert_one({
                    "_id": str(username),
                    "lower_username": str(username.lower()),
                    "uuid": str(user.get("uuid", uid.uuid())),
                    "created": int(user.get("created", int(time.time()))),
                    "pswd": str(user.get("pswd")),
                    "lvl": int(user.get("lvl", 0)),
                    "banned_until": (-1 if user.get("banned") else None),
                    "theme": str(user.get("theme", "orange")),
                    "mode": bool(user.get("mode", True)),
                    "layout": str(user.get("layout", "new")),
                    "debug": bool(user.get("debug", False)),
                    "sfx": bool(user.get("sfx", True)),
                    "bgm": bool(user.get("bgm", True)),
                    "bgm_song": int(user.get("bgm_song", 2)),
                    "pfp_data": int(user.get("pfp_data", 1)),
                    "quote": str(user.get("quote", ""))
                })
            except Exception as e:
                logging.error(f"Failed to migrate user {username}: {str(e)}")
            else:
                usernames.add(username)
                lower_usernames.add(username.lower())
        del lower_usernames
    except Exception as e:
        logging.error(f"Failed to migrate users: {str(e)}")

    # Migrate chats
    try:
        logging.info("Migrating chats...")
        chat_ids = set()
        for chat_id in os.listdir("./Meower/Storage/Chats/Indexes"):
            try:
                f = open(f"./Meower/Storage/Chats/Indexes/{chat_id}", "r")
                chat = ujson.load(f)
                f.close()
                if chat["owner"] not in usernames:
                    continue
                db.chats.insert_one({
                    "_id": chat_id,
                    "nickname": chat["nickname"],
                    "owner": chat["owner"],
                    "members": [],
                    "invite_code": secrets.token_urlsafe(5),
                    "created": int(time.time())
                })
            except Exception as e:
                logging.error(f"Failed to migrate chat {chat_id}: {str(e)}")
            else:
                chat_ids.add(chat_id)
    except Exception as e:
        logging.error(f"Failed to migrate chats: {str(e)}")

    # Migrate chat members
    try:
        logging.info("Migrating chat members...")
        for username in os.listdir("./Meower/Storage/Chats/UserIndexes"):
            try:
                for chat_name in os.listdir(f"./Meower/Storage/Chats/UserIndexes/{username}"):
                    try:
                        f = open(f"./Meower/Storage/Chats/UserIndexes/{username}/{chat_name}", "r")
                        membership = ujson.load(f)
                        f.close()
                        db.chats.update_one({"_id": membership["chat_uuid"]}, {"$addToSet": {"members": username}})
                    except Exception as e:
                        logging.error(f"Failed to migrate chat membership for {username} on chat {chat_name}: {str(e)}")
            except Exception as e:
                logging.error(f"Failed to migrate chat memberships for {username}: {str(e)}")
    except Exception as e:
        logging.error(f"Failed to migrate chat members: {str(e)}")

    # Migrate home posts
    try:
        logging.info("Migrating home posts...")
        for post_id in os.listdir("./Meower/Storage/Categories/Home/Messages"):
            try:
                f = open(f"./Meower/Storage/Categories/Home/Messages/{post_id}", "r")
                post = ujson.load(f)
                f.close()
                ts = post["t"]
                ts = datetime(year=int(ts["y"]), month=int(ts["mo"]), day=int(ts["d"]),
                                hour=int(ts["h"]), minute=int(ts["mi"]), second=int(ts["s"]))
                db.posts.insert_one({
                    "_id": uid.uuid(),
                    "type": 1,
                    "origin": "home",
                    "author": str(post["u"]),
                    "content": str(post["p"]),
                    "time": int(ts.timestamp()),
                    "deleted_at": (int(time.time()) if post["isDeleted"] else None)
                })
            except Exception as e:
                logging.error(f"Failed to migrate home post {post_id}: {str(e)}")
    except Exception as e:
        logging.error(f"Failed to migrate home posts: {str(e)}")

    # Migrate chat messages
    try:
        logging.info("Migrating chat messages...")
        for message_id in os.listdir("./Meower/Storage/Chats/Messages"):
            try:
                f = open(f"./Meower/Storage/Chats/Messages/{message_id}", "r")
                message = ujson.load(f)
                f.close()
                ts = message["t"]
                ts = datetime(year=int(ts["y"]), month=int(ts["mo"]), day=int(ts["d"]),
                                hour=int(ts["h"]), minute=int(ts["mi"]), second=int(ts["s"]))
                db.posts.insert_one({
                    "_id": uid.uuid(),
                    "type": 1,
                    "origin": str(message["chatid"]),
                    "author": str(message["u"]),
                    "content": str(message["p"]),
                    "time": int(ts.timestamp())
                })
            except Exception as e:
                logging.error(f"Failed to migrate chat message {message_id}: {str(e)}")
    except Exception as e:
        logging.error(f"Failed to migrate chat messages: {str(e)}")

    # Migrate IP bans
    try:
        logging.info("Migrating IP bans...")
        f = open(f"./Meower/Jail/IPBanlist.json", "r")
        ip_bans = ujson.load(f)
        f.close()
        for ip_address in ip_bans["wildcard"]:
            try:
                if ip_address == "127.0.0.1":
                    continue
                db.networks.insert_one({
                    "_id": ip_address,
                    "banned": True
                })
            except Exception as e:
                logging.error(f"Failed to migrate IP ban of {ip_address}: {str(e)}")
        for username, ip_address in ip_bans["users"].items():
            try:
                db.users.update_one({"_id": username}, {"$set": {"last_ip": ip_address}})
                db.networks.update_one({"_id": ip_address}, {
                    "$addToSet": {"users": username},
                    "$set": {"last_user": username}
                })
            except:
                pass
    except Exception as e:
        logging.error(f"Failed to migrate IP bans: {str(e)}")

    # Migrate filter
    try:
        logging.info("Migrating filter config...")
        f = open(f"./Meower/Config/filter.json", "r")
        filter_config = ujson.load(f)
        f.close()
        db.config.insert_one({
            "_id": "filter",
            "whitelist": filter_config["whitelist"],
            "blacklist": filter_config["blacklist"]
        })
    except Exception as e:
        logging.error(f"Failed to migrate filter config: {str(e)}")


def migrate_from_v1(db):
    # Migrate users
    try:
        logging.info("Migrating users...")
        usernames = set()
        lower_usernames = set()
        for user in db.usersv0.find({}):
            username = str(user["_id"])
            if username.lower() in lower_usernames:
                raise Exception("Duplicate username")
            else:
                lower_usernames.add(username.lower())
            try:
                db.users.insert_one({
                    "_id": str(username),
                    "lower_username": str(username.lower()),
                    "uuid": str(user.get("uuid", uid.uuid())),
                    "created": int(user.get("created", int(time.time()))),
                    "pswd": str(user.get("pswd")),
                    "lvl": int(user.get("lvl", 0)),
                    "last_ip": user.get("last_ip"),
                    "banned_until": (-1 if user.get("banned") else None),
                    "unread_inbox": bool(user("unread_inbox", False)),
                    "theme": str(user.get("theme", "orange")),
                    "mode": bool(user.get("mode", True)),
                    "layout": str(user.get("layout", "new")),
                    "debug": bool(user.get("debug", False)),
                    "sfx": bool(user.get("sfx", True)),
                    "bgm": bool(user.get("bgm", True)),
                    "bgm_song": int(user.get("bgm_song", 2)),
                    "pfp_data": int(user.get("pfp_data", 1)),
                    "quote": str(user.get("quote", ""))
                })
            except Exception as e:
                logging.error(f"Failed to migrate user {username}: {str(e)}")
            else:
                usernames.add(username)
        del lower_usernames
        db.usersv0.drop()
        db.usersv1.drop()
    except Exception as e:
        logging.error(f"Failed to migrate users: {str(e)}")
    
    # Migrate networks
    try:
        logging.info("Migrating networks...")
        for network in db.netlog.find({}):
            ip_address = str(network["_id"])
            try:
                db.networks.insert_one(network)
            except Exception as e:
                logging.error(f"Failed to migrate network {ip_address}: {str(e)}")
        db.netlog.drop()
    except Exception as e:
        logging.error(f"Failed to migrate networks: {str(e)}")

    # Migrate chats
    try:
        logging.info("Migrating chats...")
        chat_ids = set()
        for chat in db.chats.find({}):
            chat_id = str(chat["_id"])
            try:
                if chat["owner"] not in usernames:
                    db.chats.delete_one({"_id": chat_id})
                new_chat = {
                    "_id": str(chat_id),
                    "nickname": str(chat["nickname"]),
                    "owner": str(chat["owner"]),
                    "members": list(set(chat["members"])),
                    "invite_code": secrets.token_urlsafe(5),
                    "created": int(time.time())
                }
                for member in new_chat["members"]:
                    if member not in usernames:
                        new_chat["members"].remove(member)
                if len(new_chat["members"]) == 0:
                    db.chats.delete_one({"_id": chat_id})
                db.chats.find_one_and_replace({"_id": chat_id}, new_chat)
            except Exception as e:
                logging.error(f"Failed to migrate chat {chat_id}: {str(e)}")
                db.chats.delete_one({"_id": chat_id})
            else:
                chat_ids.add(chat_id)
    except Exception as e:
        logging.error(f"Failed to migrate chats: {str(e)}")

    # Migrate posts
    try:
        logging.info("Migrating posts...")
        post_ids = set()
        for post in db.posts.find({}):
            post_id = str(post["_id"])
            try:
                if (post["post_origin"] != "home") and (post["post_origin"] not in chat_ids):
                    db.posts.delete_one({"_id": post_id})
                if post["u"] not in usernames:
                    db.posts.delete_one({"_id": post_id})
                new_post = {
                    "_id": str(post_id),
                    "type": int(post["type"]),
                    "origin": str(post["post_origin"]),
                    "author": str(post["u"]),
                    "time": int(post["t"]["e"]),
                    "content": str(post["p"])
                }
                if "unfiltered_p" in post:
                    new_post["unfiltered_content"] = str(post["unfiltered_p"])
                if post.get("isDeleted"):
                    new_post["deleted_at"] = int(time.time())
                    new_post["mod_deleted"] = bool(post.get("mod_deleted") == True)
                db.posts.find_one_and_replace({"_id": post_id}, new_post)
            except Exception as e:
                logging.error(f"Failed to migrate post {post_id}: {str(e)}")
                db.posts.delete_one({"_id": post_id})
            else:
                post_ids.add(post_id)
    except Exception as e:
        logging.error(f"Failed to migrate posts: {str(e)}")

    # Migrate reports
    try:
        logging.info("Migrating reports...")
        for report in db.reports.find({}):
            report_id = str(report["_id"])
            try:
                if (report_id not in usernames) and (report_id not in post_ids):
                    db.reports.delete_one({"_id": report_id})
                db.reports.update_one({"_id": report_id}, {"$set": {
                    "score": 0,
                    "created": int(time.time())
                }})
            except Exception as e:
                logging.error(f"Failed to migrate report {report_id}: {str(e)}")
                db.reports.delete_one({"_id": report_id})
    except Exception as e:
        logging.error(f"Failed to migrate reports: {str(e)}")

    # Migrate IP bans
    try:
        logging.info("Migrating IP bans...")
        ip_bans = db.config.find_one({"_id": "IPBanlist"})
        for ip_address in ip_bans["wildcard"]:
            try:
                if ip_address == "127.0.0.1":
                    continue
                db.networks.update_one({"_id": ip_address}, {"$set": {
                    "banned": True
                }})
            except Exception as e:
                logging.error(f"Failed to migrate IP ban of {ip_address}: {str(e)}")
        for username, ip_address in ip_bans["users"].items():
            db.networks.update_one({"_id": ip_address}, {"$addToSet": {"users": username}})
    except Exception as e:
        logging.error(f"Failed to migrate IP bans: {str(e)}")

    # Migrate status
    try:
        logging.info("Migrating status...")
        status = db.config.find_one({"_id": "status"})
        if status.get("repair_mode"):
            events.redis.set("repair_mode", "")  # really bad solution to circulr import error, but it works
    except Exception as e:
        logging.error(f"Failed to migrate status: {str(e)}")

    # Clear unnecessary config items
    try:
        logging.info("Clearing unnecessary config items...")
        for config_name in [config_item["_id"] for config_item in db.config.find({}, projection={"_id": 1})]:
            if config_name not in ["filter"]:
                db.config.delete_one({"_id": config_name})
    except Exception as e:
        logging.error(f"Failed to clear unnecessary config items: {str(e)}")

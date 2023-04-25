from datetime import datetime
from copy import copy
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
				db.netlog.insert_one({
					"_id": ip_address,
					"banned": True
				})
			except Exception as e:
				logging.error(f"Failed to migrate IP ban of {ip_address}: {str(e)}")
		for username, ip_address in ip_bans["users"].items():
			try:
				db.users.update_one({"_id": username}, {"$set": {"last_ip": ip_address}})
				db.netlog.update_one({"_id": ip_address}, {
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
		users = list(db.usersv0.find({}))
		usernames = []
		lower_usernames = set()
		for i, user in enumerate(copy(users)):
			username = str(user.get("_id"))
			try:
				if username.lower() in lower_usernames:
					raise Exception("Duplicate username")
				users[i] = {
					"_id": str(username),
					"lower_username": str(username.lower()),
					"uuid": str(user.get("uuid", uid.uuid())),
					"created": int(user.get("created", int(time.time()))),
					"pswd": str(user.get("pswd")),
					"lvl": int(user.get("lvl", 0)),
					"last_ip": user.get("last_ip"),
					"banned_until": (-1 if user.get("banned") else None),
					"unread_inbox": bool(user.get("unread_inbox", False)),
					"theme": str(user.get("theme", "orange")),
					"mode": bool(user.get("mode", True)),
					"layout": str(user.get("layout", "new")),
					"debug": bool(user.get("debug", False)),
					"sfx": bool(user.get("sfx", True)),
					"bgm": bool(user.get("bgm", True)),
					"bgm_song": int(user.get("bgm_song", 2)),
					"pfp_data": int(user.get("pfp_data", 1)),
					"quote": str(user.get("quote", ""))
				}
			except Exception as e:
				logging.error(f"Failed to migrate user {username}: {str(e)}")
				users[i] = {}
			else:
				print(username)
				usernames.append(username)
				lower_usernames.add(username.lower())
		del lower_usernames
		db.users.insert_many(users)
		db.users.delete_many({"lower_username": {"$exists": False}})
		db.usersv0.drop()
		db.usersv1.drop()
	except Exception as e:
		logging.error(f"Failed to migrate users: {str(e)}")

	# Migrate chats
	try:
		logging.info("Migrating chats...")
		chats = list(db.chats.find({}))
		chat_ids = []
		for i, chat in enumerate(copy(chats)):
			chat_id = str(chat.get("_id"))
			try:
				if chat["owner"] not in usernames:
					raise Exception("Chat owner no longer exists")
				if len(chat["members"]) == 0:
					raise Exception("Members list is empty")
				for j, username in enumerate(chat["members"]):
					if username not in usernames:
						del chat["members"][j]
				chat["members"] = list(dict.fromkeys(chat["members"]))
				chat["invite_code"] = secrets.token_urlsafe(5)
				chat["created"] = int(time.time())
				chats[i] = chat
			except Exception as e:
				logging.error(f"Failed to migrate chat {chat_id}: {str(e)}")
				chats[i] = {}
			else:
				chat_ids.append(chat_id)
		db.chats.drop()
		db.chats.insert_many(chats)
		db.chats.delete_many({"nickname": {"$exists": False}})
	except Exception as e:
		logging.error(f"Failed to migrate chats: {str(e)}")

	# Migrate posts
	try:
		logging.info("Migrating posts...")
		db.posts.delete_many({"$or": [
			{
				"post_origin": {"$nin": (["home"] + chat_ids)}
			},
			{
				"u": {"$nin": usernames}
			}
		]})
		db.posts.update_many({"isDeleted": True}, {"$set": {"deleted_at": int(time.time())}})
		db.posts.update_many({}, [{
			"$set": {
				"time": "$t.e"
			},
			"$rename": {
				"post_origin": "origin",
				"u": "author",
				"p": "content",
				"unfiltered_p": "unfiltered_content"
			},
			"$unset": {
				"t": "",
				"post_id": "",
				"isDeleted": ""
			}
		}])
	except Exception as e:
		logging.error(f"Failed to migrate posts: {str(e)}")

	# Migrate reports
	try:
		logging.info("Migrating reports...")
		db.reports.update_many({}, {"$set": {
			"score": 0,
			"created": int(time.time())
		}})
	except Exception as e:
		logging.error(f"Failed to migrate reports: {str(e)}")

	# Migrate IP bans
	try:
		logging.info("Migrating IP bans...")
		ip_bans = db.config.find_one({"_id": "IPBanlist"})
		db.netlog.update_many({"_id": {"$in": ip_bans.get("wildcard", [])}}, {"$set": {
			"banned": True
		}})
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
		db.config.delete_many({"_id": {"$nin": ["filter"]}})
	except Exception as e:
		logging.error(f"Failed to clear unnecessary config items: {str(e)}")

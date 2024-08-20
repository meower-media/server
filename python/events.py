"""
This module connects the API to the websocket server.
"""

from typing import Any

import msgpack

from database import rdb, db
from supporter import Supporter

OpCreateUser  = 0
OpUpdateUser  = 1
OpDeleteUser  = 2
OpUpdateUserSettings  = 3

OpRevokeSession  = 4

OpUpdateRelationship  = 5

OpCreateChat  = 6
OpUpdateChat  = 7
OpDeleteChat  = 8

OpCreateChatMember  = 9
OpUpdateChatMember  = 10
OpDeleteChatMember  = 11

OpCreateChatEmote  = 12
OpUpdateChatEmote  = 13
OpDeleteChatEmote  = 14

OpTyping  = 15

OpCreatePost       = 16
OpUpdatePost       = 17
OpDeletePost       = 18
OpBulkDeletePosts  = 19

OpPostReactionAdd     = 20
OpPostReactionRemove  = 21

class Events:
	def __init__(self):
		# noinspection PyTypeChecker
		self.supporter: Supporter = None

	def add_supporter(self, supporter: Supporter):
		self.supporter = supporter

	def parse_post_meowid(self, post: dict[str, Any], include_replies: bool = True):
		post = list(self.supporter.parse_posts_v0([post], include_replies=include_replies, include_revisions=False))[0]

		match post["post_origin"]:
			case "home":
				chat_id = 0
			case "livechat":
				chat_id = 1
			case "inbox":
				chat_id = 2
			case _:
				chat_id = db.get_collection("chats").find_one({"_id": post["post_origin"]}, projection={"meowid": 1})[
					"meowid"]

		replys = []
		if include_replies:
			replys = [reply["meowid"] for reply in post["reply_to"]]

		return {
			"id": post["meowid"],
			"chat_id": chat_id,
			"author_id": post["author"]["meowid"],
			"reply_to_ids": replys,
			"emoji_ids": [emoji["id"] for emoji in post["emojis"]],
			"sticker_ids": post["stickers"],
			"attachments": post["attachments"],
			"content": post["p"],
			"reactions": [{
				"emoji": reaction["emoji"],
				"count": reaction["count"]
			} for reaction in post["reactions"]],
			"last_edited": post.get("edited_at", 0),
			"pinned": post["pinned"]
		}

	@staticmethod
	def parse_user_meowid(partial_user: dict[str, Any]):
		quote = db.get_collection("usersv0").find_one({"_id": partial_user["_id"]}, projection={"quote": 1})["quote"]
		return {
			"id": partial_user["meowid"],
			"username": partial_user["_id"],
			"flags": partial_user["flags"],
			"avatar": partial_user["avatar"],
			"legacy_avatar": partial_user["pfp_data"],
			"color": partial_user["avatar_color"],
			"quote": quote
		}

	def send_post_event(self, original_post: dict[str, Any]):
		post = self.parse_post_meowid(original_post, include_replies=True)

		users = [self.parse_user_meowid(post["author"])]

		replies = {}
		for reply in post["reply_to_ids"]:
			replies[reply] = self.parse_post_meowid(db.get_collection("posts").find_one({"meowid": reply}),
			                                        include_replies=False)
			users.append(self.parse_user_meowid(replies[reply]["author"]))

		emotes = {}
		for emoji in post["emoji_ids"]:
			emotes[emoji["_id"]] = {
				"id": emoji["_id"],
				"chat_id": db.get_collection("chats").find_one({"_id": emoji["chat_id"]}, projection={"meowid": 1})[
					"meowid"],
				"name": emoji["name"],
				"animated": emoji["animated"],
			}

		data = {
			"post": post,
			"reply_to": replies,
			"emotes": emotes,
			"attachments": original_post["attachments"],
			"author": users,
		}

		is_dm = db.get_collection("chats").find_one({"_id": original_post["post_origin"], "owner": None},
		                                            projection={"meowid": 1})
		if is_dm:
			data["dm_to"] = db.get_collection("users") \
				.find_one({"_id": original_post["author"]["_id"]}, projection={"meowid": 1}) \
				["meowid"]

			data["dm_chat"] = None  # unspecifed

		if "nonce" in original_post:
			data["nonce"] = original_post["nonce"]

		self.send_event(OpCreatePost, data)

	@staticmethod
	def send_event(event: int, data: dict[str, any]):
		payload = bytearray(msgpack.packb(data))
		payload.insert(0, event)

		rdb.publish("events", payload)


events = Events()

from copy import copy

from src.common.util import events
from src.common.database import redis


class CL3Events:
	def __init__(self, cl_server):
		self.cl = cl_server

		events.add_event_listener(self.__event_handler__)

	async def __event_handler__(self, event: str, payload: dict):
		if event == "pmsg":
			await self.cl.send_to_user(payload["username"], {
				"cmd": "pmsg",
				"origin": payload["origin"],
				"val": payload["val"]
			})

		elif event == "pvar":
			await self.cl.send_to_user(payload["username"], {
				"cmd": "pvar",
				"origin": payload["origin"],
				"name": payload["name"],
				"val": payload["val"]
			})

		elif event == "kick_user":
			for client in copy(self.cl.users.get(payload["username"], set())):
				try:
					await self.cl.kick_client(client, code=payload.get("code"))
				except:
					pass

		elif event == "kick_network":
			for client in copy(self.cl.clients):
				if client.ip != payload["ip"]:
					continue
				try:
					await self.cl.kick_client(client, code=payload.get("code"))
				except:
					pass

		elif event == "update_server":
			if payload.get("repair_mode", False):
				redis.set("repair_mode", "")
				for client in self.cl.clients:
					try:
						await self.cl.kick_client(client)
					except:
						pass
		
		elif event == "update_config":
			# Extract username
			username = payload["_id"]

			# Check if user is banned
			if payload["banned"]:
				for client in self.cl.users.get(username, set()):
					await self.cl.kick_client(client, code="Banned")

			# Set invisible state
			if payload["invisible"] and (username not in self.cl.invisible_users):
				self.cl.invisible_users.add(username)
				await self.cl.broadcast({"cmd": "ulist", "val": self.cl.ulist})
			elif (not payload["invisible"]) and (username in self.cl.invisible_users):
				self.cl.invisible_users.remove(username)
				await self.cl.broadcast({"cmd": "ulist", "val": self.cl.ulist})

			# Announce update to other clients
			await self.cl.send_to_user(username, {
				"cmd": "direct",
				"val": {
					"mode": "update_config",
					"payload": payload
				}
			})

		elif event == "create_post":
			if payload["post_origin"] == "home":
				_payload = {
					"cmd": "direct",
					"val": payload
				}
				_payload["val"]["mode"] = 1
				await self.cl.broadcast(_payload)
			elif payload["post_origin"] == "inbox":
				_payload = {
					"cmd": "direct",
					"val": {
						"mode": "inbox_message",
						"payload": payload
					}
				}
				if payload["u"] == "Server":
					await self.cl.broadcast(_payload)
				else:
					await self.cl.send_to_user(payload["u"], _payload)
			else:
				_payload = {
					"cmd": "direct",
					"val": payload
				}
				_payload["val"]["state"] = 2
				await self.cl.send_to_chat(payload["post_origin"], _payload)

		elif event == "update_post":
			if payload["isDeleted"]:
				_payload = {
					"cmd": "direct",
					"val": {
						"mode": "delete",
						"id": payload["_id"]
					}
				}
			else:
				_payload = {
					"cmd": "direct",
					"val": payload
				}
				_payload["val"]["mode"] = "update_post"

			# Relay post update
			if payload["post_origin"] == "home":
				await self.cl.broadcast(_payload)
			elif payload["post_origin"] == "inbox":
				if payload["u"] == "Server":
					await self.cl.broadcast(_payload)
				else:
					await self.cl.send_to_user(payload["u"], _payload)
			else:
				await self.cl.send_to_chat(payload["post_origin"], _payload)

		elif event == "update_chat":
			# Add/remove members from chat event subscription
			chat_id = payload["_id"]
			members = set(payload["members"])
			for client in copy(self.cl.chats.get(chat_id, set())):
				if client.username not in members:
					self.cl.unsubscribe_from_chat(client, chat_id)
					await self.cl.send_to_client(client, {
						"cmd": "direct",
						"val": {
							"mode": "delete",
							"id": chat_id
						}
					})
			for username in members:
				for client in copy(self.cl.users.get(username, set())):
					self.cl.subscribe_to_chat(client, chat_id)

			# Send update event
			await self.cl.send_to_chat(chat_id, {
				"cmd": "direct",
				"val": {
					"mode": "update_chat",
					"payload": payload
				}
			})

		elif event == "update_chat_state":
			await self.cl.send_to_chat(payload["chatid"], {
				"cmd": "direct",
				"val": payload
			})

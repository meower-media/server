import ipaddress
import requests
import time

from src.common.util import config, errors, events
from src.common.database import db


class Network:
	def __init__(
		self,
		_id: str,
		range: str = None,
		users: list = [],
		last_user: str = None,
		proxy: bool = None,
		country: str = None,
		banned: bool = False,
		last_used: int = None
	):
		self.ip = _id
		self.range = range
		self.users = users
		self.last_user = last_user
		self.proxy = proxy
		self.country = country
		self.banned = banned
		self.last_used = last_used

	@property
	def admin(self):
		return {
			"_id": self.ip,
			"ip": self.ip,
			"users": self.users,
			"last_user": self.last_user,
			"proxy": self.proxy,
			"country": self.country,
			"banned": self.banned,
			"last_used": (self.last_used if self.last_used else None)
		}

	def log_user(self, username: str):
		# Update network
		if username not in self.users:
			self.users.append(username)
		self.last_user = username
		self.last_used = int(time.time())
		db.netlog.update_one({"_id": self.ip}, {
			"$addToSet": {"users": username},
			"$set": {"last_user": self.last_user, "last_used": self.last_used}
		})

		# Update user
		db.users.update_one({"_id": username}, {"$set": {"last_ip": self.ip}})

	def set_ban_state(self, banned: bool):
		# Set ban status
		self.banned = banned
		db.netlog.update_one({"_id": self.ip}, {"$set": {"banned": self.banned}})

		# Kick users if network was banned
		if self.banned:
			events.send_event("kick_network", {
				"ip": self.ip,
				"code": "IPBanned"
			})
	
	def delete(self):
		db.netlog.delete_one({"_id": self.ip})


def get_iphub_data(ip_address: str) -> dict:
	if config.iphub_key:
		iphub_resp = requests.get(f"https://v2.api.iphub.info/ip/{ip_address}",
								headers={"X-Key": config.iphub_key})
		if iphub_resp.status_code == 200:
			iphub_data = iphub_resp.json()
		else:
			iphub_data = {}
	else:
		iphub_data = {}

	return iphub_data


def get_network(ip_address: str) -> Network:
	# Get IP range
	ip_obj = ipaddress.ip_address(ip_address)
	if ip_obj.version == 4:
		ip_range = str(ipaddress.IPv4Network(ip_obj.exploded + "/24", strict=False))
	elif ip_obj.version == 6:
		ip_range = str(ipaddress.IPv6Network(ip_obj.exploded + "/32", strict=False))
	else:
		raise errors.IllegalIP

	# Get network from database
	network = db.netlog.find_one({"_id": ip_address})

	# Create network if it doesn't exist or update network if it doesn't have IPHub data
	if not network:
		iphub_data = get_iphub_data(ip_address)
		network = {
			"_id": ip_address,
			"range": ip_range,
			"users": [],
			"last_user": None,
			"proxy": (iphub_data.get("block") == 1),
			"country": iphub_data.get("countryName"),
			"banned": False,
			"range_banned": False
		}
		db.netlog.insert_one(network)
	elif "country" not in network:
		iphub_data = get_iphub_data(ip_address)
		if ("block" in iphub_data) and ("countryName" in iphub_data):
			network["proxy"] = (iphub_data.get("block") == 1)
			network["country"] = iphub_data.get("countryName")
			db.netlog.update_one({"_id": ip_address}, {"$set": {
				"proxy": network["proxy"],
				"country": network["country"]
			}})
	
	# Sync IP range ban
	if (not network.get("range_banned")) and (db.netlog.count_documents({"range": ip_range, "range_banned": True}) > 0):
		network["range_banned"] = True
		db.netlog.update_one({"_id": ip_address}, {"$set": {"range_banned": True}})

	# Return network object
	return Network(**network)

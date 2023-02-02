from datetime import datetime
import requests
import os

from src.util import uid
from src.entities import users
from src.database import db

IPHUB_KEY = os.getenv("IPHUB_KEY")

class Network:
    def __init__(
        self,
        _id: str,
        ip_address: str,
        country: str = None,
        asn: str = None,
        vpn: bool = False,
        blocked: bool = False,
        creation_blocked: bool = False,
        first_used: datetime = None,
        last_used: datetime = None
    ):
        self.id = _id
        self.ip_address = ip_address
        self.country = country
        self.asn = asn
        self.vpn = vpn
        self.blocked = blocked
        self.creation_blocked = creation_blocked
        self.first_used = first_used
        self.last_used = last_used

    @property
    def admin(self):
        return {
            "id": self.id,
            "ip_address": self.ip_address,
            "country": self.country,
            "asn": self.asn,
            "vpn": self.vpn,
            "blocked": self.blocked,
            "creation_blocked": self.creation_blocked,
            "first_used": int(self.first_used.timestamp()),
            "last_used": int(self.last_used.timestamp())
        }

    @property
    def users(self):
        return [users.get_user(netlog["user_id"]) for netlog in db.netlog.find({"ip_address": self.ip_address})]

    def set_block_state(self, blocked: bool):
        self.blocked = blocked
        db.networks.update_one({"_id": self.id}, {"$set": {"blocked": self.blocked}})
    
    def set_creation_block_state(self, creation_blocked: bool):
        self.creation_blocked = creation_blocked
        db.networks.update_one({"_id": self.id}, {"$set": {"creation_blocked": self.creation_blocked}})

    def update_last_used(self):
        self.last_used = uid.timestamp()
        db.networks.update_one({"_id": self.id}, {"$set": {"last_used": self.last_used}})
    
    def delete(self):
        db.networks.delete_one({"_id": self.id})

class Netlog:
    def __init__(
        self,
        _id: str,
        ip_address: str = None,
        user_id: str = None,
        first_used: datetime = None,
        last_used: datetime = None
    ):
        self.id = _id
        self.network = get_network(ip_address)
        self.user = users.get_user(user_id)
        self.first_used = first_used
        self.last_used = last_used

    @property
    def admin(self):
        return {
            "id": self.id,
            "network": self.network.admin,
            "user": self.user.partial,
            "first_used": int(self.first_used.timestamp()),
            "last_used": int(self.last_used.timestamp())
        }

    def update_last_used(self):
        self.last_used = uid.timestamp()
        db.netlog.update_one({"_id": self.id}, {"$set": {"last_used": self.last_used}})
    
    def delete(self):
        db.netlog.delete_one({"_id": self.id})

def get_network(ip_address: str):
    network = db.networks.find_one({"ip_address": ip_address})
    if network is None:
        if IPHUB_KEY is not None:
            iphub_info = requests.get(f"https://v2.api.iphub.info/ip/{ip_address}", headers={"X-Key": IPHUB_KEY}).json()
            network = {
                "_id": uid.snowflake(),
                "ip_address": ip_address,
                "country": iphub_info["countryName"],
                "asn": iphub_info["asn"],
                "vpn": (iphub_info["block"] == 1),
                "first_used": uid.timestamp(),
                "last_used": uid.timestamp()
            }
        else:
            network = {
                "_id": uid.snowflake(),
                "ip_address": ip_address,
                "country": None,
                "asn": None,
                "vpn": False,
                "first_used": uid.timestamp(),
                "last_used": uid.timestamp()
            }
        db.networks.insert_one(network)
    return Network(**network)

def get_netlog(ip: str, user: users.User):
    netlog = db.netlog.find_one({"ip_address": ip, "user_id": user.id})
    if netlog is None:
        netlog = {
            "_id": uid.snowflake(),
            "ip_address": ip,
            "user_id": user.id,
            "first_used": uid.timestamp(),
            "last_used": uid.timestamp()
        }
        db.netlog.insert_one(netlog)
    
    return Netlog(**netlog)

def get_all_netlogs(user: users.User):
    return [Netlog(**netlog) for netlog in db.netlog.find({"user_id": user.id})]

from datetime import datetime
import requests
import os

from src.util import status, uid
from src.entities import users
from src.database import db

IPHUB_KEY = os.getenv("IPHUB_KEY")

class Network:
    def __init__(
        self,
        _id: str,
        country: str = None,
        asn: str = None,
        vpn: bool = False,
        blocked: bool = False,
        creation_blocked: bool = False,
        first_used: datetime = None,
        last_used: datetime = None
    ):
        self.ip_address = _id
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
            "ip_address": self.ip_address,
            "country": self.country,
            "asn": self.asn,
            "vpn": self.vpn,
            "blocked": self.blocked,
            "creation_blocked": self.creation_blocked,
            "users": self.users,
            "first_used": int(self.first_used.timestamp()),
            "last_used": int(self.last_used.timestamp())
        }

    @property
    def users(self):
        return [users.get_user(netlog["_id"]["user_id"]) for netlog in db.netlog.find({"_id.ip_address": self.ip_address})]

    @property
    def user_ids(self):
        return [netlog["_id"]["user_id"] for netlog in db.netlog.find({"_id.ip_address": self.ip_address})]

    def set_block_state(self, blocked: bool):
        self.blocked = blocked
        db.networks.update_one({"_id": self.ip_address}, {"$set": {"blocked": self.blocked}})
    
    def set_creation_block_state(self, creation_blocked: bool):
        self.creation_blocked = creation_blocked
        db.networks.update_one({"_id": self.ip_address}, {"$set": {"creation_blocked": self.creation_blocked}})

    def update_last_used(self):
        self.last_used = uid.timestamp()
        db.networks.update_one({"_id": self.ip_address}, {"$set": {"last_used": self.last_used}})
    
    def delete(self):
        db.networks.delete_one({"_id": self.ip_address})

class Netlog:
    def __init__(
        self,
        _id: str,
        first_used: datetime = None,
        last_used: datetime = None
    ):
        self.user = users.get_user(_id["user_id"])
        self.network = get_network(_id["ip_address"])
        self.first_used = first_used
        self.last_used = last_used

    @property
    def admin(self):
        return {
            "user": self.user.partial,
            "network": self.network.admin,
            "first_used": int(self.first_used.timestamp()),
            "last_used": int(self.last_used.timestamp())
        }
    
    def update(self):
        self.network.update_last_used()
        self.last_used = uid.timestamp()
        db.netlog.update_one({"_id": {"user_id": self.user.id, "ip_address": self.network.ip_address}}, {"$set": {"last_used": self.last_used}})

    def delete(self):
        db.netlog.delete_one({"_id": {"user_id": self.user.id, "ip_address": self.network.ip_address}})

def get_network(ip_address: str):
    network = db.networks.find_one({"_id": ip_address})
    if network is None:
        if IPHUB_KEY:
            iphub_info = requests.get(f"https://v2.api.iphub.info/ip/{ip_address}", headers={"X-Key": IPHUB_KEY}).json()
            network = {
                "_id": ip_address,
                "country": iphub_info["countryName"],
                "asn": iphub_info["asn"],
                "vpn": (iphub_info["block"] == 1),
                "first_used": uid.timestamp(),
                "last_used": uid.timestamp()
            }
        else:
            network = {
                "_id": ip_address,
                "country": None,
                "asn": None,
                "vpn": False,
                "first_used": uid.timestamp(),
                "last_used": uid.timestamp()
            }
        db.networks.insert_one(network)
    return Network(**network)

def get_netlog(user_id: str, ip_address: str):
    # Get netlog from database
    netlog = db.netlog.find_one({"_id": {"user_id": user_id, "ip_address": ip_address}})
    
    # Return netlog object
    if netlog:
        return Netlog(**netlog)
    else:
        raise status.resourceNotFound

def get_all_netlogs(user_id: str):
    return [Netlog(**netlog) for netlog in db.netlog.find({"_id.user_id": user_id})]

def update_netlog(user_id: str, ip_address: str):
    try:
        netlog = get_netlog(user_id, ip_address)
    except status.resourceNotFound:
        netlog = {
            "_id": {"user_id": user_id, "ip_address": ip_address},
            "first_used": uid.timestamp(),
            "last_used": uid.timestamp()
        }
        db.netlog.insert_one(netlog)
        netlog = Netlog(**netlog)
    else:
        netlog.update()
    
    return netlog

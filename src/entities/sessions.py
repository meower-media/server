from datetime import datetime
from base64 import b64encode, b64decode

from src.util import uid, bitfield, flags, security
from src.entities import users, accounts, networks
from src.database import db, redis

class UserSession:
    def __init__(
        self,
        _id: str,
        version: int = 0,
        user_id: str = None,
        device: dict = {},
        init_ip: str = None,
        last_ip: str = None,
        created: datetime = None,
        last_used: datetime = None
    ):
        self.id = _id
        self.version = version
        self.user = users.get_user(user_id)
        self.device = device
        self.init_ip = init_ip
        self.last_ip = last_ip
        self.created = created
        self.last_used = last_used

    @property
    def signed_token(self):
        encoded_data = b64encode(f"0:{self.id}:{str(self.version)}".encode()).decode()
        signature = security.sign(encoded_data)
        return f"{encoded_data}.{signature}"

    def refresh(self, device: dict, network: networks.Network):
        self.version += 1
        self.device = device
        self.last_ip = network.ip_address
        self.last_used = uid.timestamp()
        redis.set(f"us:{self.id}:{str(self.version)}", self.user.id, ex=1800)
        redis.expire(f"us:{self.id}:{str(self.version-1)}", 5)
        db.sessions.update_one({"_id": self.id}, {"$set": {
            "version": self.version,
            "device": self.device,
            "last_ip": self.last_ip,
            "last_used": self.last_used
        }})

    def revoke(self):
        db.sessions.delete_one({"_id": self.id})
        redis.delete(f"us:{self.id}:{str(self.version)}")

def create_user_session(account: accounts.Account, device: dict, network: networks.Network):
    session_data = {
        "_id": uid.snowflake(),
        "version": 0,
        "user_id": account.id,
        "device": device,
        "init_ip": network.ip_address,
        "last_ip": network.ip_address,
        "created": uid.timestamp(),
        "last_used": uid.timestamp()
    }
    session = UserSession(**session_data)
    redis.set(f"us:{session.id}:{str(session.version)}", session.user.id, ex=1800)
    db.sessions.insert_one(session_data)
    return session

def get_user_by_token(token: str):
    data, signature = token.split(".")
    if not security.valid_signature(signature, data):
        return None
    
    ttype, session_id, version = b64decode(data.encode()).decode().split(":")
    user_id = redis.get(f"us:{session_id}:{str(version)}").decode()
    if user_id is None:
        return None
    
    user = users.get_user(user_id)
    if bitfield.has(user.flags, flags.user.deleted) or bitfield.has(user.flags, flags.user.terminated):
        return None
    else:
        return user

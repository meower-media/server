from datetime import datetime
from base64 import b64encode, b64decode

from src.util import status, uid, events, security, email
from src.entities import users, accounts, networks, applications
from src.database import db, redis

SESSION_SCOPES = [
    "profile.read",
    "profile.write",
    "account.read",
    "inbox.read",
    "inbox.mark",
    "sync.read",
    "sync.write",
    "applications.read",
    "applications.write",
    "posts.read",
    "posts.write",
    "comments.read",
    "comments.write",
    "chats.read",
    "chats.write",
    "messages.read",
    "messages.write"
]

class UserSession:
    def __init__(
        self,
        _id: str,
        version: int = 0,
        user_id: str = None,
        device: dict = {},
        ip_address: str = None,
        last_refreshed: datetime = None,
        created: datetime = None
    ):
        self.id = _id
        self.version = version
        self.user = users.get_user(user_id)
        self.device = device
        self.ip_address = ip_address
        self.last_refreshed = last_refreshed
        self.created = created

    @property
    def client(self):
        return {
            "id": self.id,
            "user": self.user.partial,
            "device": self.device,
            "ip_address": self.ip_address,
            "last_refreshed": (int(self.last_refreshed.timestamp()) if self.last_refreshed else None),
            "created": (int(self.created.timestamp()) if self.created else None)
        }

    @property
    def signed_token(self):
        encoded_data = b64encode(f"1:{self.id}:{str(self.version)}".encode())
        signature = security.sign_data(encoded_data)
        return f"{encoded_data.decode()}.{signature.decode()}"

    def refresh(self, device: dict, network: networks.Network):
        self.version += 1
        self.device = device
        self.ip_address = network.ip_address
        self.last_refreshed = uid.timestamp()
        redis.set(f"ses:{self.id}:{str(self.version)}", self.user.id, ex=3600)
        redis.expire(f"ses:{self.id}:{str(self.version-1)}", 5)
        db.sessions.update_one({"_id": self.id}, {"$set": {
            "version": self.version,
            "device": self.device,
            "ip_address": self.ip_address,
            "last_refreshed": self.last_refreshed
        }})
        events.emit_event("session_updated", self.user.id, {
            "id": self.id,
            "version": self.version,
            "device": self.device,
            "ip_address": self.ip_address,
            "last_refreshed": int(self.last_refreshed.timestamp())
        })

    def revoke(self):
        db.sessions.delete_one({"_id": self.id})
        for key in redis.keys(f"ses:{self.id}:*"):
            redis.delete(key.decode())
        events.emit_event("session_deleted", self.user.id, {
            "id": self.id
        })

class OAuthSession:
    def __init__(
        self,
        _id: str,
        version: int = 0,
        user_id: str = None,
        application_id: str = None,
        scopes: int = 0,
        ip_address: str = None,
        last_refreshed: datetime = None,
        created: datetime = None
    ):
        self.id = _id
        self.version = version
        self.user = users.get_user(user_id)
        self.application = applications.get_application(application_id)
        self.scopes = scopes
        self.ip_address = ip_address
        self.last_refreshed = last_refreshed
        self.created = created

    @property
    def signed_token(self):
        encoded_data = b64encode(f"1:{self.id}:{str(self.version)}".encode())
        signature = security.sign_data(encoded_data)
        return f"{encoded_data.decode()}.{signature.decode()}"

    def refresh(self, device: dict, network: networks.Network):
        self.version += 1
        self.device = device
        self.ip_address = network.ip_address
        self.last_refreshed = uid.timestamp()
        redis.set(f"ses:{self.id}:{str(self.version)}", self.user.id, ex=3600)
        redis.expire(f"ses:{self.id}:{str(self.version-1)}", 5)
        db.sessions.update_one({"_id": self.id}, {"$set": {
            "version": self.version,
            "device": self.device,
            "ip_address": self.ip_address,
            "last_refreshed": self.last_refreshed
        }})
        events.emit_event("session_updated", self.user.id, {
            "id": self.id,
            "version": self.version,
            "device": self.device,
            "ip_address": self.ip_address,
            "last_refreshed": int(self.last_refreshed.timestamp())
        })

    def revoke(self):
        db.sessions.delete_one({"_id": self.id})
        for key in redis.keys(f"ses:{self.id}:*"):
            redis.delete(key.decode())
        events.emit_event("session_deleted", self.user.id, {
            "id": self.id
        })

class BotSession:
    def __init__(
        self,
        _id: str,
        version: int = None,
        user_id: str = None
    ):
        self.id = _id
        self.version = version
        self.user = users.get_user(user_id)

def create_user_session(account: accounts.Account, device: dict, network: networks.Network):
    session = {
        "_id": uid.snowflake(),
        "user_id": account.id,
        "created": uid.timestamp()
    }
    db.sessions.insert_one(session)
    session = UserSession(**session)
    session.refresh(device, network)

    events.emit_event("session_created", account.id, session.client)

    if account.id not in network.user_ids:
        networks.update_netlog(session.user, network)
        if account.email:
            email.send_email(account.email, session.user.username, "new_login_location", {
                "username": session.user.username,
                "client": device.get("client_name", "Meower"),
                "ip_address": network.ip_address,
                "country": network.country
            })

    return session

def get_user_session(session_id: str):
    # Get session from database
    session = db.sessions.find_one({"_id": session_id})

    # Return session object
    if session:
        return UserSession(**session)
    else:
        raise status.resourceNotFound

def get_all_user_sessions(user: any):
    return [UserSession(**session) for session in db.sessions.find({"user_id": user.id})]

def revoke_all_user_sessions(user: any):
    for session in get_all_user_sessions(user):
        session.revoke()

def get_user_by_token(token: str):
    try:
        # Decode signed token
        token_metadata, signature = token.split(".")
        token_metadata = token_metadata.encode()
        signature = signature.encode()
        ttype, session_id, version = b64decode(token_metadata).decode().split(":")

        # Check token signature
        if not security.validate_signature(signature, token_metadata):
            return None

        # Return user
        if ttype == "1":  # regular user
            user_id = redis.get(f"ses:{session_id}:{version}")
            if user_id:
                return users.get_user(user_id.decode())
            else:
                return None
        elif ttype == "3":  # bot user
            user = users.get_user(session_id)
            if str(user.bot_session) != str(version):
                return None
            else:
                return user
        else:
            return None
    except:
        return None

def get_session_by_token(token: str):
    try:
        # Decode signed token
        token_metadata, signature = token.split(".")
        token_metadata = token_metadata.encode()
        signature = signature.encode()
        ttype, session_id, version = b64decode(token_metadata).decode().split(":")

        # Check token signature
        if not security.validate_signature(signature, token_metadata):
            return None

        # Return session
        if ttype == "1":
            return get_user_session(session_id)
        elif ttype == "3":
            user = users.get_user(session_id)
            if str(user.bot_session) != str(version):
                return None
            else:
                return BotSession(_id=session_id, version=version, user_id=user.id)
        else:
            return None
    except:
        return None

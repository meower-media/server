from datetime import datetime
from base64 import b64encode, b64decode
from hashlib import sha256
import secrets

from src.util import status, uid, events, security, bitfield, email
from src.entities import users, accounts, networks, applications
from src.database import db, redis

OAUTH_SCOPES = [
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
        created: datetime = None,
        legacy_token: str = None
    ):
        self.id = _id
        self.version = version
        self.user = users.get_user(user_id)
        self.device = device
        self.network = (networks.get_network(ip_address) if ip_address else None)
        self.last_refreshed = last_refreshed
        self.created = created
        self.legacy_token = legacy_token

    @property
    def client(self):
        return {
            "id": self.id,
            "user": self.user.partial,
            "device": self.device,
            "country": self.network.country,
            "last_refreshed": (int(self.last_refreshed.timestamp()) if self.last_refreshed else None),
            "created": (int(self.created.timestamp()) if self.created else None)
        }

    @property
    def signed_token(self):
        encoded_data = b64encode(f"1:{self.id}:{str(self.version)}".encode())
        signature = security.sign_data(encoded_data)
        return f"{encoded_data.decode()}.{signature.decode()}"

    def refresh(self, device: dict, ip_address: str):
        self.version += 1
        self.device = device
        self.network = networks.get_network(ip_address)
        self.last_refreshed = uid.timestamp()
        if self.legacy_token:
            legacy_token = secrets.token_urlsafe(64)
            self.legacy_token = sha256(legacy_token.encode()).hexdigest()
            db.sessions.update_one({"_id": self.id}, {"$set": {
                "version": self.version,
                "device": self.device,
                "ip_address": self.network.ip_address,
                "last_refreshed": self.last_refreshed,
                "legacy_token": self.legacy_token
            }})
        else:
            redis.set(f"ses:{self.id}:{str(self.version)}", self.user.id, ex=3600)
            redis.expire(f"ses:{self.id}:{str(self.version-1)}", 5)
            db.sessions.update_one({"_id": self.id}, {"$set": {
                "version": self.version,
                "device": self.device,
                "ip_address": self.network.ip_address,
                "last_refreshed": self.last_refreshed
            }})
        events.emit_event("session_updated", self.user.id, self.client)

        if self.legacy_token:
            return legacy_token

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
        application_id: str = None,
        user_id: str = None,
        scopes: list|int = [],
        ip_address: str = None,
        last_refreshed: datetime = None,
        created: datetime = None
    ):
        self.id = _id
        self.version = version
        self.application = applications.get_application(application_id)
        self.user = users.get_user(user_id)
        if isinstance(scopes, list):
            self.scopes = scopes
        else:
            self.scopes = []
            for i in range((len(OAUTH_SCOPES)-1)):
                if bitfield.has(scopes, i):
                    self.scopes.append(OAUTH_SCOPES[i])
        self.ip_address = ip_address
        self.last_refreshed = last_refreshed
        self.created = created

    @property
    def signed_token(self):
        encoded_data = b64encode(f"2:{self.id}:{str(self.version)}".encode())
        signature = security.sign_data(encoded_data)
        return f"{encoded_data.decode()}.{signature.decode()}"

    @property
    def encoded_scopes(self):
        return bitfield.create([OAUTH_SCOPES.index(scope) for scope in self.scopes])

    def refresh(self, network: networks.Network):
        self.version += 1
        self.ip_address = network.ip_address
        self.last_refreshed = uid.timestamp()
        redis.set(f"oas:{self.id}:{str(self.version)}", f"{self.application.id}:{self.user.id}:{str(self.encoded_scopes)}", ex=3600)
        redis.expire(f"oas:{self.id}:{str(self.version-1)}", 5)
        db.oauth_sessions.update_one({"_id": self.id}, {"$set": {
            "version": self.version,
            "ip_address": self.ip_address,
            "last_refreshed": self.last_refreshed
        }})

    def revoke(self):
        db.oauth_sessions.delete_one({"_id": self.id})
        for key in redis.keys(f"oas:{self.id}:*"):
            redis.delete(key.decode())

class AuthorizedApp:
    def __init__(
        self,
        _id: str,
        scopes: list = [],
        first_authorized: datetime = None,
        last_authorized: datetime = None
    ):
        self.id = _id
        self.application = applications.get_application(_id["application_id"])
        self.user_id = _id["user_id"]
        self.scopes = scopes
        self.first_authorized = first_authorized
        self.last_authorized = last_authorized

    @property
    def client(self):
        return {
            "id": self.id,
            "application": self.application.public,
            "scopes": self.scopes,
            "first_authorized": int(self.first_authorized.timestamp()),
            "last_authorized": (int(self.last_authorized.timestamp()) if self.last_authorized else None)
        }

    def update(self, scopes: list):
        self.scopes += scopes
        self.scopes = list(set(self.scopes))
        self.last_authorized = uid.timestamp()
        db.authorized_apps.update_one({"_id": self.id}, {"$set": {
            "scopes": self.scopes,
            "last_authorized": self.last_authorized
        }})
        events.emit_event("authorized_app_created", self.user_id, {
            "id": self.id,
            "scopes": self.scopes,
            "last_authorized": int(self.last_authorized.timestamp())
        })

    def delete(self):
        db.authorized_apps.delete_one({"_id": self.id})
        for session in get_all_oauth_sessions(self.application.id, self.user_id):
            session.revoke()

class BotSession:
    def __init__(
        self,
        _id: str,
        version: int = None
    ):
        self.id = _id
        self.version = version
        self.user = users.get_user(self.id)

        if self.version != self.user.bot_session:
            self = None

def create_user_session(account: accounts.Account, device: dict, ip_address: str, legacy: bool = False):
    session = {
        "_id": uid.snowflake(),
        "version": 0,
        "user_id": account.id,
        "device": device,
        "ip_address": ip_address,
        "last_refreshed": uid.timestamp(),
        "created": uid.timestamp()
    }
    if legacy:
        legacy_token = secrets.token_urlsafe(64)
        session["legacy_token"] = sha256(legacy_token.encode()).hexdigest()
    
    db.sessions.insert_one(session)
    session = UserSession(**session)
    if not legacy:
        redis.set(f"ses:{session.id}:{str(session.version)}", session.user.id, ex=3600)
    events.emit_event("session_created", account.id, session.client)

    if (account.id not in session.network.user_ids) and account.email:
        email.send_email(account.email, session.user.username, "new_login_location", {
            "username": session.user.username,
            "client": device.get("client_name", "Meower"),
            "ip_address": session.network.ip_address,
            "country": session.network.country
        })
    networks.update_netlog(session.user.id, session.network.ip_address)

    if legacy:
        return legacy_token, session
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

def create_oauth_session(application_id: str, user_id: str, scopes: list, ip_address: str):
    session = {
        "_id": uid.snowflake(),
        "application_id": application_id,
        "user_id": user_id,
        "scopes": scopes,
        "ip_address": ip_address,
        "created": uid.timestamp()
    }
    db.oauth_sessions.insert_one(session)
    session = OAuthSession(**session)
    redis.set(f"oas:{session.id}:{str(session.version)}", f"{session.application.id}:{session.user.id}:{str(session.encoded_scopes)}", ex=3600)

    try:
        authorized_app = get_authorized_app(application_id, user_id)
    except status.resourceNotFound:
        authorized_app = create_authorized_app(application_id, user_id)
    authorized_app.update(scopes)

    return session

def get_oauth_session(session_id: str):
    # Get session from database
    session = db.oauth_sessions.find_one({"_id": session_id})

    # Return session object
    if session:
        return OAuthSession(**session)
    else:
        raise status.resourceNotFound

def get_all_oauth_sessions(application_id: str, user_id: str):
    return [OAuthSession(**session) for session in db.oauth_sessions.find({"application_id": application_id, "user_id": user_id})]

def create_authorized_app(application_id: str, user_id: str):
    authorized_app = {
        "_id": {"application_id": application_id, "user_id": user_id},
        "first_authorized": uid.timestamp()
    }
    db.authorized_apps.insert_one(authorized_app)
    authorized_app = AuthorizedApp(**authorized_app)
    events.emit_event("authorized_app_created", user_id, authorized_app.client)
    return authorized_app

def get_authorized_app(application_id: str, user_id: str):
    # Get authorized app details from database
    authorized_app = db.authorized_apps.find_one({"_id": {"application_id": application_id, "user_id": user_id}})

    # Return authorized app object
    if authorized_app:
        return AuthorizedApp(**authorized_app)
    else:
        raise status.resourceNotFound

def get_partial_session_by_token(token: str):
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
            user_id = redis.get(f"ses:{session_id}:{version}")
            if user_id:
                return UserSession(_id=session_id, version=int(version), user_id=user_id.decode())
            else:
                return None
        elif ttype == "2":
            session_details = redis.get(f"oas:{session_id}:{version}")
            if session_details:
                application_id, user_id, scopes = session_details.decode().split(":")
                return OAuthSession(_id=session_id, version=int(version), application_id=application_id, user_id=user_id, scopes=int(scopes))
            else:
                return None
        elif ttype == "3":
            return BotSession(_id=session_id, version=int(version))
        else:
            return None
    except:
        return None

def get_session_by_token(token: str, legacy: bool = False):
    if legacy:
        # Get session from database
        session = db.sessions.find_one({"legacy_token": sha256(token.encode()).hexdigest()})

        # Return session object
        if session:
            return UserSession(**session)
        else:
            raise status.resourceNotFound
    else:
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
            elif ttype == "2":
                return get_oauth_session(session_id)
            elif ttype == "3":
                return BotSession(_id=session_id, version=int(version))
            else:
                return None
        except:
            return None

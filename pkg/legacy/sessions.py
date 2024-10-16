from typing import Optional, TypedDict, Literal, Any
from base64 import urlsafe_b64encode, urlsafe_b64decode
from hashlib import sha256
import uuid, time, msgpack, pymongo, hmac

from database import db, rdb, signing_keys
import security, errors


TOKEN_TYPES = Literal[
    "acc",   # account authorization
    "email", # email actions (such as email verification or account recovery)
]


class AccSessionDB(TypedDict):
    _id: str
    user: str
    ip: str
    user_agent: str
    created_at: int
    refreshed_at: int


class AccSessionV0(TypedDict):
    _id: str
    ip: str
    location: str
    user_agent: str
    created_at: int
    refreshed_at: int


class AccSession:
    def __init__(self, data: AccSessionDB):
        self._db = data

    @classmethod
    def create(cls: "AccSession", user: str, ip: str, user_agent: str) -> "AccSession":
        # restore account if it is pending deletion
        result = db.usersv0.update_one({"_id": user}, {"$set": {"delete_after": None}})
        if result.modified_count:
            rdb.publish("admin", msgpack.packb({
                "op": "alert_user",
                "user": user,
                "content": "Your account was scheduled for deletion but you logged back in. Your account is no longer scheduled for deletion! If you didn't request for your account to be deleted, please change your password immediately."
            }))

        data: AccSessionDB = {
            "_id": str(uuid.uuid4()),
            "user": user,
            "ip": ip,
            "user_agent": user_agent,
            "created_at": int(time.time()),
            "refreshed_at": int(time.time())
        }
        db.acc_sessions.insert_one(data)

        #security.log_security_action("session_create", user, {
        #    "session_id": data["_id"],
        #    "ip": ip,
        #    "user_agent": user_agent
        #})

        return cls(data)

    @classmethod
    def get_by_id(cls: "AccSession", session_id: str) -> "AccSession":
        data: Optional[AccSessionDB] = db.acc_sessions.find_one({"_id": session_id})
        if not data:
            raise errors.AccSessionNotFound

        return cls(data)

    @classmethod
    def get_by_token(cls: "AccSession", token: str) -> "AccSession":
        session_id, _, expires_at = extract_token(token, "acc")
        if expires_at < int(time.time()):
            raise errors.AccSessionTokenExpired
        return cls.get_by_id(session_id)

    @classmethod
    def get_username_by_token(cls: "AccSession", token: str) -> str:
        session_id, _, expires_at = extract_token(token, "acc")
        if expires_at < int(time.time()):
            raise errors.AccSessionTokenExpired
        username = rdb.get(session_id)
        if username:
            return username.decode()
        else:
            session = cls.get_by_id(session_id)
            username = session.username
            rdb.set(session_id, username, ex=300)
            return username

    @classmethod
    def get_all(cls: "AccSession", user: str) -> list["AccSession"]:
        return [
            cls(data)
            for data in db.acc_sessions.find(
                {"user": user},
                sort=[("refreshed_at", pymongo.DESCENDING)]
            )
        ]

    @property
    def id(self) -> str:
        return self._db["_id"]

    @property
    def token(self) -> str:
        return create_token("acc", [
            self._db["_id"],
            self._db["refreshed_at"],
            self._db["refreshed_at"]+(86400*21)  # expire token after 3 weeks
        ])

    @property
    def username(self):
        return self._db["user"]

    @property
    def v0(self) -> AccSessionV0:
        return {
            "_id": self._db["_id"],
            "ip": self._db["ip"],
            "location": "",
            "user_agent": self._db["user_agent"],
            "created_at": self._db["created_at"],
            "refreshed_at": self._db["refreshed_at"]
        }

    def refresh(self, ip: str, user_agent: str, check_token: Optional[str] = None):
        if check_token:
            # token re-use prevention
            _, refreshed_at, _ = security.extract_token(check_token, "acc")
            if refreshed_at != self._db["refreshed_at"]:
                return self.revoke()

        self._db.update({
            "ip": ip,
            "user_agent": user_agent,
            "refreshed_at": int(time.time())
        })
        db.acc_sessions.update_one({"_id": self._db["_id"]}, {"$set": self._db})

        #security.log_security_action("session_refresh", self._db["user"], {
        #    "session_id": self._db["_id"],
        #    "ip": ip,
        #    "user_agent": user_agent
        #})

    def revoke(self):
        db.acc_sessions.delete_one({"_id": self._db["_id"]})
        rdb.delete(f"u{self._db['_id']}")
        rdb.publish("admin", msgpack.packb({
            "op": "revoke_acc_session",
            "user": self._db["user"],
            "sid": self._db["_id"]
        }))

        #security.log_security_action("session_revoke", self._db["user"], {
        #    "session_id": self._db["_id"]
        #})


class EmailTicket:
    def __init__(
        self,
        email_address: str,
        username: str,
        action: Literal["verify", "recover", "lockdown"],
        expires_at: int
    ):
        self.email_address = email_address
        self.username = username
        self.action = action
        self.expires_at = expires_at

        if self.expires_at < int(time.time()):
            raise errors.EmailTicketExpired

    @classmethod
    def get_by_token(cls: "EmailTicket", token: str) -> "EmailTicket":
        return cls(*extract_token(token, "email"))

    @property
    def token(self) -> str:
        return create_token("email", [
            self.email_address,
            self.username,
            self.action,
            self.expires_at
        ])


def create_token(ttype: TOKEN_TYPES, claims: Any) -> str:
    # Encode claims
    encoded_claims = msgpack.packb(claims)

    # Sign encoded claims
    signature = hmac.digest(signing_keys[ttype], encoded_claims, digest=sha256)

    # Construct token
    token = b".".join([urlsafe_b64encode(encoded_claims), urlsafe_b64encode(signature)])

    return token.decode()


def extract_token(token: str, expected_type: TOKEN_TYPES) -> Optional[Any]:
    # Extract data and signature
    encoded_claims, signature = token.split(".")
    encoded_claims = urlsafe_b64decode(encoded_claims)
    signature = urlsafe_b64decode(signature)

    # Check signature
    expected_signature = hmac.digest(signing_keys[expected_type], encoded_claims, digest=sha256)
    if not hmac.compare_digest(signature, expected_signature):
        raise errors.InvalidTokenSignature

    # Decode claims
    claims = msgpack.unpackb(encoded_claims)
    
    return claims

from typing import Optional, TypedDict
import uuid, time, msgpack

from database import db, rdb
import security, errors


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
        data: AccSessionDB = {
            "_id": str(uuid.uuid4()),
            "user": user,
            "ip": ip,
            "user_agent": user_agent,
            "created_at": int(time.time()),
            "refreshed_at": int(time.time())
        }
        db.acc_sessions.insert_one(data)
        return cls(data)

    @classmethod
    def get_by_id(cls: "AccSession", session_id: str) -> "AccSession":
        data: Optional[AccSessionDB] = db.acc_sessions.find_one({"_id": session_id})
        if not data:
            raise errors.SessionNotFound

        return cls(data)

    @classmethod
    def get_by_token(cls: "AccSession", token: str) -> "AccSession":
        session_id, _ = security.extract_token(token, "acc")
        return cls.get_by_id(session_id)

    @classmethod
    def get_username_by_token(cls: "AccSession", token: str) -> str:
        session_id, _ = security.extract_token(token, "acc")
        username = rdb.get(f"u{session_id}")
        if username:
            return username.decode()
        else:
            session = cls.get_by_id(session_id)
            username = session.username
            rdb.set(f"u{session_id}", username, ex=300)
            return username

    @classmethod
    def get_all(cls: "AccSession", user: str) -> list["AccSession"]:
        return [cls(data) for data in db.acc_sessions.find({"user": user})]

    @property
    def token(self) -> str:
        return security.create_token("acc", [self._db["_id"], self._db["refreshed_at"]])

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
            _, refreshed_at = security.extract_token(check_token, "acc")
            if refreshed_at != self._db["refreshed_at"]:
                return self.revoke()

        self._db.update({
            "ip": ip,
            "user_agent": user_agent,
            "refreshed_at": int(time.time())
        })
        db.acc_sessions.update_one({"_id": self._db["_id"]}, {"$set": self._db})

    def revoke(self):
        db.acc_sessions.delete_one({"_id": self._db["_id"]})
        rdb.delete(f"u{self._db['_id']}")
        rdb.publish("admin", msgpack.packb({
            "op": "revoke_acc_session",
            "user": self._db["user"],
            "sid": self._db["_id"]
        }))

import secrets, time

import models, errors
from entities import ids
from database import db


def db_to_v0(session: models.db.Session) -> models.v0.Session:
    return {
        "_id": str(session["_id"]),
        "ip_address": session["ip_address"],
        "user_agent": session["user_agent"],
        "client": session["client"],
        "created_at": session["created_at"],
        "mfa_verified": session["mfa_verified"],
        "revoked": session["revoked"]
    }

def create_session(user_id: int, ip_address: str, user_agent: str = "", client: str = "") -> models.db.Session:
    session: models.db.Session = {
        "_id": ids.gen_id(),
        "token": secrets.token_urlsafe(32),
        "user_id": user_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "client": client,
        "created_at": int(time.time()),
        "mfa_verified": False,
        "revoked": False
    }
    db.sessions.insert_one(session)
    return session

def get_session(session_id: int) -> models.db.Session:
    session: models.db.Session = db.sessions.find_one({"_id": session_id})
    if session:
        return session
    else:
        raise errors.SessionNotFound

def get_session_by_token(token: str) -> models.db.Session:
    session: models.db.Session = db.sessions.find_one({"token": token})
    if session:
        return session
    else:
        raise errors.SessionNotFound

def refresh_session(
    session_id: int,
    ip_address: str,
    user_agent: str = "",
    client: str = ""
) -> models.db.Session:
    session: models.db.Session = db.sessions.find_one({
        "_id": session_id,
        "revoked": False
    })
    if not session:
        raise errors.SessionNotFound
    
    session.update({
        "token": secrets.token_urlsafe(32),
        "ip_address": ip_address,
        "user_agent": user_agent,
        "client": client
    })
    db.sessions.update_one({"_id": session_id}, {"$set": session})

    return session

def verify_mfa(session_id: int):
    result = db.sessions.update_one({"_id": session_id, "revoked": False}, {"$set": {
        "mfa_verified": True
    }})
    if result.matched_count < 1:
        raise errors.SessionNotFound

def revoke_session(session_id: int):
    result = db.sessions.update_one({"_id": session_id, "revoked": False}, {"$set": {
        "revoked": True
    }})
    if result.matched_count < 1:
        raise errors.SessionNotFound

from quart import Blueprint, request
from quart_schema import validate_response
from pydantic import BaseModel, Field
from typing import Literal

import models
from entities import sessions
from .utils import auto_ratelimit, check_auth


session_bp = Blueprint("session_bp", __name__, url_prefix="/session")


class SessionResponse(BaseModel):
    error: Literal[False] = Field()
    session: models.v0.Session = Field()
    token: str = Field()


@session_bp.get("/")
@check_auth(mfa_bypass=True, return_session=True, return_user=False)
@validate_response(SessionResponse)
async def get_session(session: models.db.Session):
    return {
        "error": False,
        "session": sessions.db_to_v0(session),
        "token": session["token"]
    }, 200

@session_bp.delete("/")
@check_auth(mfa_bypass=True, return_session=True, return_user=False)
async def revoke_session(session: models.db.Session):
    sessions.revoke_session(session["_id"])
    return {"error": False}, 200

@session_bp.post("/refresh")
@auto_ratelimit("session", "ip", 5, 120)
@check_auth(mfa_bypass=True, return_session=True, return_user=False)
@validate_response(SessionResponse)
async def refresh_session(session: models.db.Session):
    session = sessions.refresh_session(
        session["_id"],
        request.ip,
        user_agent=request.headers.get("User-Agent", ""),
        client=request.headers.get("X-Client", ""),
    )
    return {
        "error": False,
        "session": sessions.db_to_v0(session),
        "token": session["token"]
    }, 200

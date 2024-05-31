import time
from quart import Blueprint, request
from quart_schema import validate_request
from pydantic import BaseModel, Field
from typing import Optional

import errors
from entities import users, sessions
from .utils import auto_ratelimit


auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")


class RegisterBody(BaseModel):
    username: str = Field(pattern=users.USERNAME_REGEX)
    password: str = Field(min_length=8, max_length=72)
    captcha: Optional[str] = Field(default=None)

class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=255)

class ResetPasswordBody(BaseModel):
    email: str = Field()


@auth_bp.post("/register")
@validate_request(RegisterBody)
@auto_ratelimit("session", "ip", 5, 120)
@auto_ratelimit("registration", "ip", 5, 900)
async def create_user(data: RegisterBody):
    try:
        user = users.create_user(data.username, data.password)
    except errors.UsernameExists:
        return {"error": True, "type": "usernameExists"}, 409
    else:
        session = sessions.create_session(
            user["_id"],
            request.ip,
            user_agent=request.headers.get("User-Agent", ""),
            client=request.headers.get("X-Client", ""),
        )
        return {
            "error": False,
            "user": users.db_to_v0(user, True),
            "session": sessions.db_to_v0(session),
            "token": session["token"]
        }, 200

@auth_bp.post("/login")
@validate_request(LoginBody)
@auto_ratelimit("session", "ip", 5, 120)
async def login(data: LoginBody):
    try:
        user = users.get_user_by_username(data.username)
    except errors.UserNotFound:
        raise errors.InvalidCredentials
    else:
        # Check password
        if not users.check_password_hash(data.password, user["password"]):
            raise errors.InvalidCredentials

        # Check ban
        if user["ban"].get("state") == "perm_ban" or \
            (user["ban"].get("state") == "temp_ban" and \
                user["ban"].get("expires") > int(time.time())):
            raise errors.UserBanned(ban=user["ban"])

        # Create session
        session = sessions.create_session(
            user["_id"],
            request.ip,
            user_agent=request.headers.get("User-Agent", ""),
            client=request.headers.get("X-Client", ""),
        )

        return {
            "error": False,
            "user": users.db_to_v0(user, True),
            "session": sessions.db_to_v0(session),
            "token": session["token"]
        }, 200

@auth_bp.post("/reset-password")
@validate_request(ResetPasswordBody)
@auto_ratelimit("reset-password", "ip", 2, 900)
async def reset_password(data: ResetPasswordBody):
    try:
        user = users.get_user_by_email(data.email)
        users.send_password_reset_email(user["_id"], user["email"])
    except errors.UserNotFound:
        pass
    
    return {"error": False}, 200

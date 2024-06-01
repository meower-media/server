import time
from typing import Optional, Callable, Any, Literal
from functools import wraps
from quart import current_app, request, abort
from quart_schema import validate_headers
from pydantic import BaseModel, Field

import errors, security
from entities import sessions, users


class TokenHeader(BaseModel):
    token: str = Field()


def check_auth(
    mfa_bypass: bool = False,
    check_restrictions: Optional[int] = None,
    return_session: bool = False,
    return_user: bool = True
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @validate_headers(TokenHeader)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get token
            token: str = request.headers["token"]

            # Get session
            session = sessions.get_session_by_token(token)
            if session["revoked"]:
                raise errors.SessionNotFound
            if (not mfa_bypass) and (not session["mfa_verified"]):
                raise errors.MFANotVerified

            # Get user
            user = users.get_user(session["user_id"])

            # Check ban
            if user["ban"].get("state") == "perm_ban" or \
                (user["ban"].get("state") == "temp_ban" and \
                    user["ban"].get("expires") > int(time.time())):
                raise errors.UserBanned(ban=user["ban"])

            # Check restrictions
            if check_restrictions and (user["ban"].get("restrictions", 0) & check_restrictions):
                if user["ban"].get("state") == "perm_restriction" or \
                    (user["ban"].get("state") == "temp_restriction" and \
                        user["ban"].get("expires") > int(time.time())):
                    raise errors.UserBanned(ban=user["ban"])

            # Add session and user to kwargs
            if return_session:
                kwargs["session"] = session
            if return_user:
                kwargs["user"] = user

            # Remove headers from kwargs
            if "headers" in kwargs:
                del kwargs["headers"]

            return await current_app.ensure_async(func)(*args, **kwargs)

        return wrapper
    
    return decorator

def auto_ratelimit(bucket: str, identifier: Literal["global", "user", "ip"], limit: int, seconds: int) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            _bucket = bucket
            # Create ratelimit bucket
            if identifier == "user":
                _bucket += str(kwargs["requester"]["_id"])
            elif identifier == "ip":
                _bucket += request.ip

            # Check ratelimit
            if security.ratelimited(_bucket):
                raise errors.Ratelimited
            
            # Ratelimit
            security.ratelimit(_bucket, limit, seconds)

            return await current_app.ensure_async(func)(*args, **kwargs)

        return wrapper
    
    return decorator

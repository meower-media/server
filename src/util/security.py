from base64 import b64encode, b64decode
from hashlib import sha512
from sanic.response import HTTPResponse, json
from functools import wraps
import secrets
import hmac
import requests
import os

from src.util import status, logging, bitfield
from src.entities import sessions, infractions
from src.database import redis

CAPTCHA_PROVIDERS = {
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
    "hcaptcha": "https://hcaptcha.com/siteverify",
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify"
}

CAPTCHA_URI = CAPTCHA_PROVIDERS.get(os.getenv("CAPTCHA_PROVIDER"))
CAPTCHA_SECRET = os.getenv("CAPTCHA_SECRET")

if redis.exists("signing_key") != 1:
    logging.warn("No signing key! Generating new signing key...")
    redis.set("signing_key", secrets.token_urlsafe(2048))
SIGNING_KEY = redis.get("signing_key")

RATELIMIT_LIMITS = {  # these are not good at all right now
    "register": {
        "hits": 2,
        "seconds": 60
    },
    "login": {
        "hits": 5,
        "seconds": 60
    },
    "mfa": {
        "hits": 5,
        "seconds": 60
    },
    "verify": {
        "hits": 5,
        "seconds": 60
    },
    "change_relationship": {
        "hits": 5,
        "seconds": 10
    },
    "open_chat": {
        "hits": 5,
        "seconds": 10
    },
    "update_chat": {
        "hits": 5,
        "seconds": 10
    },
    "typing": {
        "hits": 3,
        "seconds": 1
    },
    "search": {
        "hits": 5,
        "seconds": 10
    },
    "create_post": {
        "hits": 1,
        "seconds": 2
    },
    "edit_post": {
        "hits": 1,
        "seconds": 2
    },
    "reputation": {
        "hits": 2,
        "seconds": 1
    },
    "create_comment": {
        "hits": 1,
        "seconds": 2
    },
    "edit_comment": {
        "hits": 1,
        "seconds": 2
    },
    "create_message": {
        "hits": 5,
        "seconds": 5
    },
    "edit_message": {
        "hits": 5,
        "seconds": 5
    }
}

def check_captcha(captcha_response: str, ip_address: str):
    if not CAPTCHA_URI:
        logging.warn("No captcha provider set! Skipping captcha check...")
        return True

    return requests.get(CAPTCHA_URI, data={
        "secret": CAPTCHA_SECRET,
        "response": captcha_response,
        "remoteip": ip_address
    }).json().get("success", False)

def sign_data(data: bytes):
    return b64encode(hmac.new(key=SIGNING_KEY, msg=data, digestmod=sha512).digest())

def validate_signature(signature: bytes, data: bytes):
    return hmac.compare_digest(b64decode(signature), hmac.new(key=SIGNING_KEY, msg=data, digestmod=sha512).digest())

def auto_ratelimit(key: str, identifier: str):
    # Get remaining limit
    remaining = redis.get(f"rtl:{key}:{identifier}")
    expires = redis.ttl(f"rtl:{key}:{identifier}")
    if remaining:
        remaining = int(remaining.decode())
        expires = int(expires)
    else:
        remaining = RATELIMIT_LIMITS[key]["hits"]
        expires = RATELIMIT_LIMITS[key]["seconds"]

    # Check whether ratelimit has been exceeded
    if remaining <= 0:
        raise status.ratelimited

    # Set new remaining count
    remaining -= 1
    redis.set(f"rtl:{key}:{identifier}", str(remaining), ex=expires)

    return (key, remaining, expires)

def v0_protected(
        ignore_suspension: bool = True,
        ignore_ban: bool = False
    ):
        def decorator(func: callable) -> callable:
            @wraps(func)
            def wrapper(request, *args, **kwargs) -> HTTPResponse:
                # Extract username and token
                username = request.headers.get("Username", "")
                token = request.headers.get("Token", "")
                if len(username) > 20:
                    username = username[:20]
                if len(token) > 255:
                    token = token[:255]

                # Get session and user
                request.ctx.session = sessions.get_session_by_token(token, legacy=True)
                if request.ctx.session and (request.ctx.session.user.username == username):
                    request.ctx.user = request.ctx.session.user
                else:
                    return json({"error": True, "type": "Unauthorized"}, status=401)

                # Check whether the user is banned/suspended
                user_moderation_status = infractions.user_status(request.ctx.user)
                if ((not ignore_suspension) and user_moderation_status["suspended"]) or ((not ignore_ban) and user_moderation_status["banned"]):
                    raise status.userRestricted

                return func(request, *args, **kwargs)
            return wrapper
        return decorator

def v1_protected(
        require_auth: bool = True,
        ratelimit_key: str = None,
        ratelimit_scope: str = None,
        allow_bots: bool = True,
        oauth_scope: str = None,
        admin_scope: int = None,
        ignore_suspension: bool = True,
        ignore_ban: bool = False
    ):
        def decorator(func: callable) -> callable:
            @wraps(func)
            def wrapper(request, *args, **kwargs) -> HTTPResponse:
                # Get user from access token
                if request.token:
                    request.ctx.session = sessions.get_partial_session_by_token(request.token)
                    if request.ctx.session:
                        request.ctx.user = request.ctx.session.user
                    else:
                        raise status.notAuthenticated
                elif require_auth or oauth_scope or admin_scope:
                    raise status.notAuthenticated
                else:
                    request.ctx.user = None

                # Check ratelimit
                if ratelimit_key and ratelimit_scope:
                    if ratelimit_scope == "global":
                        identifier = "global"
                    elif ratelimit_scope == "ip":
                        identifier = request.ip
                    elif ratelimit_scope == "user":
                        identifier = request.ctx.user.id
                    else:
                        identifier = ratelimit_scope
                    
                    (key, remaining, expires) = auto_ratelimit(ratelimit_key, identifier)
                    request.ctx.ratelimit_key = key
                    request.ctx.ratelimit_scope = ratelimit_scope
                    request.ctx.ratelimit_remaining = remaining
                    request.ctx.ratelimit_expires = expires

                if request.ctx.user:
                    # Check whether user is a bot
                    if (not allow_bots) and isinstance(request.ctx.session, sessions.BotSession):
                        raise status.missingPermissions

                    # Check whether session has required OAuth scope
                    if isinstance(request.ctx.session, sessions.OAuthSession) and (oauth_scope not in request.ctx.session.scopes):
                        raise status.missingScope

                    # Check whether user has required admin scope
                    if (admin_scope is not None) and (not bitfield.has(request.ctx.user.admin, admin_scope)):
                        raise status.missingScope

                    # Check whether the user is banned/suspended
                    user_moderation_status = infractions.user_status(request.ctx.user)
                    if ((not ignore_suspension) and user_moderation_status["suspended"]) or ((not ignore_ban) and user_moderation_status["banned"]):
                        raise status.userRestricted

                return func(request, *args, **kwargs)
            return wrapper
        return decorator

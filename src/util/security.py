from base64 import b64encode, b64decode
from hashlib import sha512
from sanic.response import HTTPResponse
import secrets
import hmac
import requests
import os

from src.util import status, logging, bitfield, flags
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
        "hits": 1,
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
        "seconds": 1
    },
    "reputation": {
        "hits": 1,
        "seconds": 1
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
    if CAPTCHA_URI is None:
        logging.warn("No captcha provider set!")
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

def sanic_protected(
        ratelimit: str = None,
        require_auth: bool = True,
        allow_bots: bool = True,
        ignore_guardian: bool = False,
        ignore_ban: bool = False,
        ignore_suspension: bool = True
    ):
        def decorator(func: callable) -> callable:
            def wrapper(request, *args, **kwargs) -> HTTPResponse:
                # Check ratelimit
                if ratelimit:
                    # Get remaining limit
                    remaining = redis.get(f"rtl:{ratelimit}:{request.ip}")
                    expires = redis.ttl(f"rtl:{ratelimit}:{request.ip}")
                    if remaining:
                        remaining = int(remaining.decode())
                        expires = int(expires)
                    else:
                        remaining = RATELIMIT_LIMITS[ratelimit]["hits"]
                        expires = RATELIMIT_LIMITS[ratelimit]["seconds"]
                    request.ctx.ratelimit_bucket = ratelimit
                    request.ctx.ratelimit_remaining = remaining
                    request.ctx.ratelimit_reset = expires

                    # Check whether ratelimit has been exceeded
                    if remaining <= 0:
                        raise status.ratelimited

                    # Set new remaining count
                    remaining -= 1
                    request.ctx.ratelimit_remaining = remaining
                    redis.set(f"rtl:{ratelimit}:{request.ip}", str(remaining), ex=expires)

                # Get user from access token
                if not request.token:
                    request.ctx.user = None
                else:
                    request.ctx.user = sessions.get_user_by_token(request.token)
                if require_auth and (not request.ctx.user):
                    raise status.notAuthenticated

                if request.ctx.user:
                    # Check whether user is a bot
                    if (not allow_bots) and bitfield.has(request.ctx.user.flags, flags.user.bot):
                        raise status.missingPermissions # placeholder

                    # Check whether user is being restricted by guardian
                    if (not ignore_guardian) and (False):
                        raise status.missingPermissions # placeholder

                    # Check whether the user is banned/suspended
                    user_moderation_status = infractions.user_status(request.ctx.user)
                    if ((not ignore_ban) and user_moderation_status["banned"]):
                        raise status.userBanned
                    elif ((not ignore_suspension) and user_moderation_status["suspended"]):
                        raise status.userSuspended

                return func(request, *args, **kwargs)
            return wrapper
        return decorator

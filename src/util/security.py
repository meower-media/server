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

RATELIMIT_LIMITS = {
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

def sanic_protected(allow_bots: bool = True, ignore_guardian: bool = False, ignore_ban: bool = False, ignore_suspension: bool = True):
    def decorator(func: callable) -> callable:
        def wrapper(request, *args, **kwargs) -> HTTPResponse:
            # Get user from access token
            token = request.headers.get("Authorization")
            if token is None:
                request.ctx.user = None
            else:
                request.ctx.user = sessions.get_user_by_token(token)
            if request.ctx.user is None:
                raise status.notAuthenticated

            # Check whether user is a bot
            if (not allow_bots) and bitfield.has(request.ctx.user, flags.user.bot):
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

def sanic_ratelimited(bucket: str):
    def decorator(func: callable) -> callable:
        def wrapper(request, *args, **kwargs) -> HTTPResponse:
            # Get remaining limit
            remaining = redis.get(f"rtl:{bucket}:{request.ip}")
            if remaining is None:
                remaining = RATELIMIT_LIMITS[bucket]["hits"]
            else:
                remaining = int(remaining.decode())

            # Check whether ratelimit has been exceeded
            if remaining <= 0:
                raise status.ratelimited

            # Set new remaining count
            remaining -= 1
            redis.set(f"rtl:{bucket}:{request.ip}", str(remaining), ex=RATELIMIT_LIMITS[bucket]["seconds"])

            return func(request, *args, **kwargs)
        return wrapper
    return decorator

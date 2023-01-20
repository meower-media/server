from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from base64 import b64encode, b64decode
from hashlib import sha256
from multipledispatch import dispatch
from sanic.response import HTTPResponse
import requests
import os

from src.util import status
from src.entities import sessions, infractions

CAPTCHA_PROVIDERS = {
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
    "hcaptcha": "https://hcaptcha.com/siteverify",
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify"
}

CAPTCHA_URI = CAPTCHA_PROVIDERS.get(os.getenv("CAPTCHA_PROVIDER"))
CAPTCHA_SECRET = os.getenv("CAPTCHA_SECRET")

PRIV_KEY = Ed25519PrivateKey.generate()
PUB_KEY = PRIV_KEY.public_key()

def check_captcha(captcha_response: str, ip_address: str):
    if CAPTCHA_URI is None:
        return True

    return requests.get(CAPTCHA_URI, data={
        "secret": CAPTCHA_SECRET,
        "response": captcha_response,
        "remoteip": ip_address
    }).json().get("success", False)

def sign(data: str):
    return b64encode(PRIV_KEY.sign(sha256(data.encode()).digest())).decode()

def valid_signature(signature: str, data: str):
    try:
        PUB_KEY.verify(b64decode(signature.encode()), sha256(data.encode()).digest())
    except:
        return False
    else:
        return True

def sanic_protected(check_suspension: bool = False):
    def decorator(func: callable) -> callable:
        def wrapper(request, *args, **kwargs) -> HTTPResponse:
            # Get user from access token
            token = request.headers.get("Authorization")
            if token is None:
                request.ctx.user = None
            else:
                request.ctx.user = sessions.get_user_by_token(token)

            # Throw error if unable to authenticate token
            if request.ctx.user is None:
                raise status.notAuthenticated

            # Check whether the user is banned/suspended
            user_moderation_status = infractions.user_status(request.ctx.user)
            if user_moderation_status["banned"]:
                raise status.userBanned
            elif (check_suspension and user_moderation_status["suspended"]):
                raise status.userSuspended

            return func(request, *args, **kwargs)
        return wrapper
    return decorator

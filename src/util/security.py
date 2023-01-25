from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from base64 import b64encode, b64decode
from hashlib import sha512
from sanic.response import HTTPResponse
import hmac
import requests
import os

from src.util import status, logging
from src.entities import sessions, infractions
from src.database import redis

CAPTCHA_PROVIDERS = {
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
    "hcaptcha": "https://hcaptcha.com/siteverify",
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify"
}

CAPTCHA_URI = CAPTCHA_PROVIDERS.get(os.getenv("CAPTCHA_PROVIDER"))
CAPTCHA_SECRET = os.getenv("CAPTCHA_SECRET")

def check_captcha(captcha_response: str, ip_address: str):
    if CAPTCHA_URI is None:
        return True

    return requests.get(CAPTCHA_URI, data={
        "secret": CAPTCHA_SECRET,
        "response": captcha_response,
        "remoteip": ip_address
    }).json().get("success", False)

def sign_data(key: bytes, data: bytes):
    return b64encode(hmac.new(key=key, msg=data, digestmod=sha512).digest())

def validate_signature(key: bytes, signature: bytes, data: bytes):
    signature = b64decode(signature)
    return hmac.compare_digest(signature, hmac.new(key=key, msg=data, digestmod=sha512).digest())

def encode_and_sign_data(key: bytes, data: str):
    encoded_data = b64encode(data.encode())
    signature = b64encode(hmac.new(key, msg=encoded_data, digestmod=sha512).digest())
    return f"{encoded_data.decode()}.{signature.decode()}"

def decode_and_validate_data(key: bytes, data: str):
    try:
        encoded_data, signature = data.split(".")
        encoded_data = encoded_data.encode()
        signature = b64decode(signature.encode())
        if hmac.compare_digest(signature, hmac.new(key, msg=encoded_data, digestmod=sha512).digest()):
            return b64decode(encoded_data).decode()
        else:
            return None
    except:
        return None

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

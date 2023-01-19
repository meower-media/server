from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from base64 import b64encode, b64decode
from hashlib import sha256
import requests
import os

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

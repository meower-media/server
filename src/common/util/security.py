from base64 import b64encode, b64decode
from hashlib import sha512
import hmac

from src.common.util import errors
from src.common.database import db, redis


# Get signing key
SIGNING_KEY = db.config.find_one({"_id": "security"})["signing_key"]


def sign_data(data: bytes):
    return b64encode(hmac.new(key=SIGNING_KEY, msg=data, digestmod=sha512).digest())


def validate_signature(signature: bytes, data: bytes):
    return hmac.compare_digest(b64decode(signature), hmac.new(key=SIGNING_KEY, msg=data, digestmod=sha512).digest())


def check_ratelimit(identifier: str, bucket: str):
    # Construct ratelimit key
    key = f"rtlm:{identifier}:{bucket}"

    # Get amount remaining
    try:
        remaining = int(redis.get(key).decode())
    except:
        remaining = 1

    # Return whether remaining is above 0
    return (remaining <= 0)


def ratelimit(identifier: str, bucket: str, limit: int, expires: int):
    # Construct ratelimit key
    key = f"rtlm:{identifier}:{bucket}"

    # Get amount remaining and expiration
    try:
        remaining = int(redis.get(key).decode())
    except:
        remaining = limit

    # Set new remaining amount
    remaining -= 1
    redis.set(key, remaining, ex=expires)


def auto_ratelimit(identifier: str, bucket: str, limit: int, expires: int):
    # Check if client is ratelimited
    if check_ratelimit(identifier, bucket):
        raise errors.Ratelimited

    # Ratelimit client
    ratelimit(identifier, bucket, limit, expires)

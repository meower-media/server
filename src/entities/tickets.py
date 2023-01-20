from base64 import b64encode, b64decode
import json
import zlib

from src.util import uid, security
from src.entities import users, accounts
from src.database import redis

TICKET_EXPIRATIONS = {
    "mfa": 300
}

def create_ticket(user: users.User|accounts.Account, type: str, data: dict = {}):
    ticket_id = uid.snowflake()
    data["t"] = type
    data["u"] = user.id
    redis.set(f"tic:{ticket_id}", zlib.compress(json.dumps(data).encode()), ex=TICKET_EXPIRATIONS[type])
    encoded_data = b64encode(f"0:{ticket_id}".encode()).decode()
    signature = security.sign(encoded_data)
    return f"{encoded_data}.{signature}"

def get_ticket_details(signed_ticket: str):
    try:
        if signed_ticket.count(".") != 1:
            return None

        encoded_data, signature = signed_ticket.split(".")
        if not security.valid_signature(signature, encoded_data):
            return None
        
        ttype, ticket_id = b64decode(encoded_data.encode()).decode().split(":")
        if ttype != "0":
            return None
        raw_data = redis.get(f"tic:{ticket_id}")
        if raw_data is None:
            return None

        decoded_data = json.loads(zlib.decompress(raw_data).decode())
        decoded_data["id"] = ticket_id
        return decoded_data
    except:
        return None

def revoke_ticket(ticket_id: str):
    redis.delete(f"tic:{ticket_id}")

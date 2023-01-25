from base64 import b64encode, b64decode
import json

from src.util import uid, security
from src.entities import users
from src.database import db, redis

TICKET_EXPIRATIONS = {
    "verification": 60,
    "mfa": 300,
    "email_verification": 3600
}

def create_ticket(user: users.User, type: str, data: dict = {}):
    # Create ticket data
    ticket_id = uid.snowflake()
    data["u"] = user.id
    data["t"] = type
    
    # Add ticket data to Redis
    redis.set(f"tick:{ticket_id}", json.dumps(data), ex=TICKET_EXPIRATIONS[type])

    # Create, sign and return ticket
    ticket_details = b64encode(f"0:{ticket_id}".encode())
    signature = security.sign_data(user.hmac_key, ticket_details)
    return f"{ticket_details.decode()}.{signature.decode()}"

def get_ticket_details(signed_ticket: str):
    try:
        # Decode signed ticket
        ticket_metadata, signature = signed_ticket.split(".")
        ticket_metadata = ticket_metadata.encode()
        signature = signature.encode()
        ticket_type, ticket_id = b64decode(ticket_metadata).decode().split(":")
        if ticket_type != "0":
            return None

        # Get ticket details
        ticket_details = redis.get(f"tick:{ticket_id}")
        if ticket_details is None:
            return None
        else:
            ticket_details = json.loads(ticket_details.decode())

        # Check ticket signature
        hmac_key = db.users.find_one({"_id": ticket_details["u"]}, projection={"hmac_key": 1})["hmac_key"]
        if not security.validate_signature(hmac_key, signature, ticket_metadata):
            return None
        else:
            ticket_details["id"] = ticket_id
            return ticket_details
    except:
        return None

def revoke_ticket(ticket_id: str):
    redis.delete(f"tick:{ticket_id}")

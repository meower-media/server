from base64 import b64encode, b64decode
import json

from src.util import uid, security
from src.entities import users
from src.database import db, redis

TICKET_EXPIRATIONS = {
    "verification": 60,
    "mfa": 300,
    "email_verification": 3600,
    "email_revert": 86400,
    "password_reset": 900,
    "parent_link": 86400
}

def create_ticket(user: users.User, type: str, data: dict = {}):
    # Create ticket data
    ticket_id = uid.snowflake()
    data["u"] = user.id
    data["t"] = type
    
    # Add ticket data to Redis
    redis.set(f"tic:{ticket_id}", json.dumps(data), ex=TICKET_EXPIRATIONS[type])

    # Create, sign and return ticket
    ticket_metadata = b64encode(f"0:{ticket_id}".encode())
    signature = security.sign_data(ticket_metadata)
    return f"{ticket_metadata.decode()}.{signature.decode()}"

def get_ticket_details(signed_ticket: str):
    try:
        # Decode signed ticket
        ticket_metadata, signature = signed_ticket.split(".")
        ticket_metadata = ticket_metadata.encode()
        signature = signature.encode()
        ttype, ticket_id = b64decode(ticket_metadata).decode().split(":")
        if ttype != "0":
            return None

        # Check ticket signature
        if not security.validate_signature(signature, ticket_metadata):
            return None

        # Get ticket details
        ticket_details = redis.get(f"tic:{ticket_id}")
        if ticket_details is None:
            return None
        else:
            return json.loads(ticket_details.decode())
    except:
        return None

def revoke_ticket(ticket_id: str):
    redis.delete(f"tic:{ticket_id}")

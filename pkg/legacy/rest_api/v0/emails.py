from quart import Blueprint, current_app as app, request, abort
from quart_schema import validate_request
from pydantic import BaseModel, Field
from hashlib import sha256
from base64 import urlsafe_b64encode
import time, secrets

from sessions import EmailTicket, AccSession
from database import db, rdb
import security, errors


emails_bp = Blueprint("emails_bp", __name__, url_prefix="/emails")


class VerifyEmailBody(BaseModel):
    token: str = Field(min_length=1, max_length=1024)

class RecoverAccountBody(BaseModel):
    token: str = Field(min_length=1, max_length=1024)
    password: str = Field(min_length=8, max_length=72)

class LockAccountBody(BaseModel):
    token: str = Field(min_length=1, max_length=1024)


@emails_bp.post("/verify")
@validate_request(VerifyEmailBody)
async def verify_email(data: VerifyEmailBody):
    # Get ticket
    try:
        ticket = EmailTicket.get_by_token(data.token)
    except errors.InvalidTokenSignature|errors.EmailTicketExpired:
        abort(401)

    # Validate action
    if ticket.action != "verify":
        abort(401)

    # Make sure the email address matches the user's pending email address
    pending_email = rdb.get(f"pe{ticket.username}")
    if (not pending_email) or (pending_email.decode() != ticket.email_address):
        abort(401)
    rdb.delete(f"pe{ticket.username}")

    # Get account
    account = db.usersv0.find_one({"_id": ticket.username}, projection={
        "_id": 1,
        "email": 1
    })

    # Log action
    security.log_security_action("email_changed", account["_id"], {
        "old_email_hash": security.get_normalized_email_hash(account["email"]) if account.get("email") else None,
        "new_email_hash": security.get_normalized_email_hash(ticket.email_address),
        "ip": request.ip,
        "user_agent": request.headers.get("User-Agent")
    })

    # Update user's email address
    db.usersv0.update_one({"_id": account["_id"]}, {"$set": {
        "email": ticket.email_address,
        "normalized_email_hash": security.get_normalized_email_hash(ticket.email_address)
    }})
    app.cl.send_event("update_config", {"email": ticket.email_address}, usernames=[account["_id"]])

    return {"error": False}, 200


@emails_bp.post("/recover")
@validate_request(RecoverAccountBody)
async def recover_account(data: RecoverAccountBody):
    # Make sure ticket hasn't already been used
    if rdb.exists(urlsafe_b64encode(sha256(data.token.encode()).digest()).decode()):
        abort(401)

    # Get ticket
    try:
        ticket = EmailTicket.get_by_token(data.token)
    except errors.InvalidTokenSignature|errors.EmailTicketExpired:
        abort(401)

    # Validate action
    if ticket.action != "recover":
        abort(401)

    # Get account
    account = db.usersv0.find_one({"_id": ticket.username}, projection={
        "_id": 1,
        "email": 1,
        "pswd": 1,
        "flags": 1
    })

    # Make sure the ticket email matches the user's current email
    if ticket.email_address != account["email"]:
        abort(401)

    # Revoke ticket
    rdb.set(
        urlsafe_b64encode(sha256(data.token.encode()).digest()).decode(),
        "",
        ex=(ticket.expires_at-int(time.time()))+1
    )

    # Update password (and remove locked flag)
    new_hash = security.hash_password(data.password)
    db.usersv0.update_one({"_id": account["_id"]}, {"$set": {
        "pswd": new_hash,
        "flags": account["flags"] ^ security.UserFlags.LOCKED
    }})

    # Log action
    security.log_security_action("password_changed", account["_id"], {
        "method": "email",
        "old_pswd_hash": account["pswd"],
        "new_pswd_hash": new_hash,
        "ip": request.ip,
        "user_agent": request.headers.get("User-Agent")
    })

    # Revoke sessions
    for session in AccSession.get_all(account["_id"]):
        session.revoke()
    
    return {"error": False}, 200


@emails_bp.post("/lockdown")
@validate_request(LockAccountBody)
async def lock_account(data: LockAccountBody):
    # Make sure ticket hasn't already been used
    if rdb.exists(urlsafe_b64encode(sha256(data.token.encode()).digest()).decode()):
        abort(401)

    # Get ticket
    try:
        ticket = EmailTicket.get_by_token(data.token)
    except errors.InvalidTokenSignature|errors.EmailTicketExpired:
        abort(401)

    # Validate action
    if ticket.action != "lockdown":
        abort(401)

    # Get account
    account = db.usersv0.find_one({"_id": ticket.username}, projection={
        "_id": 1,
        "flags": 1
    })

    # Revoke ticket
    rdb.set(
        urlsafe_b64encode(sha256(data.token.encode()).digest()).decode(),
        "",
        ex=(ticket.expires_at-int(time.time()))+1
    )

    # Make sure the account hasn't already been locked in the last 24 hours (lockdown tickets last for 24 hours)
    # This is to stop multiple identity/credential rotations by an attacker to keep access via lockdown tickets.
    if security.ratelimited(f"lock:{account['_id']}"):
        abort(429)
    security.ratelimit(f"lock:{account['_id']}", 1, 86400)

    # Update account
    db.usersv0.update_one({"_id": account["_id"]}, {"$set": {
        "email": ticket.email_address,
        "normalized_email_hash": security.get_normalized_email_hash(ticket.email_address),
        "flags": account["flags"] | security.UserFlags.LOCKED,
        "mfa_recovery_code": secrets.token_hex(5)
    }})

    # Remove authenticators
    db.authenticators.delete_many({"user": account["_id"]})

    # Log event
    security.log_security_action("locked", account["_id"], {
        "method": "email",
        "ip": request.ip,
        "user_agent": request.headers.get("User-Agent")
    })

    # Revoke sessions
    for session in AccSession.get_all(account["_id"]):
        session.revoke()

    return {"error": False}, 200

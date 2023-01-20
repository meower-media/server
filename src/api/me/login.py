from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from src.util import status
from src.entities import users, accounts, networks, sessions, tickets

v1 = Blueprint("v1_me_login", url_prefix="/login")

class PasswordForm(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=20
    )
    password: str = Field(
        min_length=1,
        max_length=255
    )
    captcha: Optional[str] = Field(
        max_length=2048
    )

class TOTPForm(BaseModel):
    ticket: str = Field(
        min_length=1
    )
    code: str = Field(
        min_length=1,
        max_length=10
    )

@v1.post("/password")
@validate(json=PasswordForm)
async def v1_login_password(request, body: PasswordForm):
    # Get user ID by email or username
    try:
        if "@" in body.username:
            user_id = accounts.get_id_from_email(body.username)
        else:
            user_id = users.get_id_from_username(body.username)
    except status.notFound:
        raise status.invalidCredentials  # Placeholder error

    # Get account and check password
    account = accounts.get_account(user_id)
    if account.locked:
        raise status.accountLocked
    if not account.check_password(body.password):
        raise status.invalidCredentials

    # Ask for MFA or complete authentication
    if account.require_mfa:
        mfa_ticket = tickets.create_ticket(account, "mfa")
        return json({
            "user_id": account.id,
            "access_token": None,
            "mfa_required": True,
            "mfa_ticket": mfa_ticket,
            "mfa_methods": account.mfa_methods
        })
    else:
        session = sessions.create_user_session(account, request.ctx.device, networks.get_network(request.ip))
        return json({
            "user_id": account.id,
            "access_token": session.signed_token,
            "mfa_required": False,
            "mfa_ticket": None,
            "mfa_methods": None
        })

@v1.post("/mfa/totp")
@validate(json=TOTPForm)
async def v1_mfa_totp(request, body: TOTPForm):
    # Get ticket details
    ticket = tickets.get_ticket_details(body.ticket)
    if (ticket is None) or (ticket["t"] != "mfa"):
        raise status.invalidTicket

    # Get account
    try:
        account = accounts.get_account(ticket["u"])
    except status.notFound:
        raise status.invalidTicket

    # Check TOTP code and complete authentication
    if not account.check_totp(body.code):
        raise status.invalidTOTP
    else:
        tickets.revoke_ticket(ticket["id"])
        session = sessions.create_user_session(account, request.ctx.device, networks.get_network(request.ip))
        return json({
            "user_id": account.id,
            "access_token": session.signed_token
        })

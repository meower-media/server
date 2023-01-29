from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from src.util import status, security
from src.entities import users, accounts, networks, sessions, tickets

v1 = Blueprint("v1_authentication", url_prefix="/auth")

class RegistrationForm(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=20
    )
    password: str = Field(
        min_length=8,
        max_length=255
    )
    child: bool = Field()
    captcha: Optional[str] = Field(
        max_length=2048
    )

class LoginPasswordForm(BaseModel):
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

class LoginTOTPForm(BaseModel):
    ticket: str = Field(
        max_length=255
    )
    code: str = Field(
        min_length=1,
        max_length=8
    )

class PasswordVerificationForm(BaseModel):
    password: str = Field(
        min_length=1,
        max_length=255
    )

class TOTPVerificationForm(BaseModel):
    totp_code: str = Field(
        min_length=1,
        max_length=8
    )

@v1.post("/register")
@validate(json=RegistrationForm)
@security.sanic_protected(ratelimit="register", require_auth=False)
async def v1_register(request, body: RegistrationForm):
    # Get network and check whether it's blocked
    network = networks.get_network(request.ip)
    if network.blocked or network.creation_blocked:
        raise status.networkBlocked

    # Check captcha
    if not security.check_captcha(body.captcha, request.ip):
        raise status.invalidCaptcha

    # Create account
    account = accounts.create_account(body.username, body.password, body.child, require_email=(len(network.users) >= 3))

    # Complete authentication
    session = sessions.create_user_session(account, request.ctx.device, network)
    return json({"user_id": account.id, "access_token": session.signed_token})

@v1.post("/password")
@validate(json=LoginPasswordForm)
@security.sanic_protected(ratelimit="login", require_auth=False)
async def v1_login_password(request, body: LoginPasswordForm):
    # Get network and check whether it's blocked
    network = networks.get_network(request.ip)
    if network.blocked:
        raise status.networkBlocked

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
    if account.mfa_enabled:
        mfa_ticket = tickets.create_ticket(account, "mfa")
        return json({
            "user_id": account.id,
            "access_token": None,
            "mfa_required": True,
            "mfa_ticket": mfa_ticket,
            "mfa_methods": account.mfa_methods
        })
    else:
        session = sessions.create_user_session(account, request.ctx.device, network)
        print(session)
        return json({
            "user_id": account.id,
            "access_token": session.signed_token,
            "mfa_required": False,
            "mfa_ticket": None,
            "mfa_methods": None
        })

@v1.post("/mfa/totp")
@validate(json=LoginTOTPForm)
@security.sanic_protected(ratelimit="mfa", require_auth=False)
async def v1_mfa_totp(request, body: LoginTOTPForm):
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

@v1.post("/verify/password")
@validate(json=PasswordVerificationForm)
@security.sanic_protected(ratelimit="verify", allow_bots=False)
async def v1_verify_password(request, body: PasswordVerificationForm):
    # Get account
    account = accounts.get_account(request.ctx.user.id)
    if account is None:
        raise status.internal
    
    # Check whether verifying via password is allowed
    if account.mfa_enabled:
        raise status.missingPermissions # placeholder

    # Verify account password
    if not account.check_password(body.password):
        raise status.invalidCredentials

    # Create and return verification ticket
    ticket = tickets.create_ticket(request.ctx.user, "verification")
    return json({"verification_ticket": ticket})

@v1.post("/verify/totp")
@validate(json=TOTPVerificationForm)
@security.sanic_protected(ratelimit="verify", allow_bots=False)
async def v1_verify_totp(request, body: TOTPVerificationForm):
    # Get account
    account = accounts.get_account(request.ctx.user.id)
    if account is None:
        raise status.internal
    
    # Check whether verifying via TOTP is allowed
    if "mfa" not in account.mfa_methods:
        raise status.totpNotEnabled

    # Verify TOTP code
    if not account.check_totp(body.totp_code):
        raise status.invalidTOTP

    # Create and return verification ticket
    ticket = tickets.create_ticket(request.ctx.user, "verification")
    return json({"verification_ticket": ticket})

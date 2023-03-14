from sanic import Blueprint, HTTPResponse, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from src.util import status, regex, security, email
from src.entities import users, accounts, networks, sessions, tickets, security_cookies

v1 = Blueprint("v1_authentication", url_prefix="/auth")


class RegistrationForm(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=20,
        regex=regex.USERNAME_VALIDATION
    )
    password: str = Field(
        min_length=8,
        max_length=255
    )
    captcha: Optional[str] = Field(
        max_length=2048
    )


class LoginPasswordForm(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=20,
        regex=regex.USERNAME_VALIDATION
    )
    password: str = Field(
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


class PasswordRecoveryForm(BaseModel):
    email: str = Field(
        max_length=255,
        #regex=regex.EMAIL_VALIDATION
    )


@v1.post("/register")
@validate(json=RegistrationForm)
@security.v1_protected(require_auth=False, ratelimit_key="register", ratelimit_scope="ip")
async def v1_register(request, body: RegistrationForm):
    # Get network and check whether it's blocked
    network = networks.get_network(request.ip)
    if network.blocked or network.creation_blocked:
        raise status.networkBlocked

    # Check captcha
    if not security.check_captcha(body.captcha, request.ip):
        raise status.invalidCaptcha

    # Create account
    account = accounts.create_account(body.username, body.password, require_email=(len(network.users) >= 3))

    # Complete authentication
    security_cookie = security_cookies.decode_security_cookie(cookie=request.cookies.get("security_cookie"))
    security_cookie.add_user(account)
    session = sessions.create_user_session(account, request.ctx.device, network.ip_address)
    resp = json({"user_id": account.id, "access_token": session.signed_token})
    resp.cookies["security_cookie"] = security_cookie.signed_cookie
    return resp


@v1.post("/password")
@validate(json=LoginPasswordForm)
@security.v1_protected(require_auth=False, ratelimit_key="login", ratelimit_scope="ip")
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
    except status.resourceNotFound:
        raise status.invalidCredentials

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
        security_cookie = security_cookies.decode_security_cookie(cookie=request.cookies.get("security_cookie"))
        security_cookie.add_user(account)
        session = sessions.create_user_session(account, request.ctx.device, network.ip_address)
        resp = json({
            "user_id": account.id,
            "access_token": session.signed_token,
            "mfa_required": False,
            "mfa_ticket": None,
            "mfa_methods": None
        })
        resp.cookies["security_cookie"] = security_cookie.signed_cookie
        return resp


@v1.post("/totp")
@validate(json=LoginTOTPForm)
@security.v1_protected(require_auth=False, ratelimit_key="mfa", ratelimit_scope="ip")
async def v1_login_totp(request, body: LoginTOTPForm):
    # Get ticket details
    ticket = tickets.get_ticket_details(body.ticket)
    if (not ticket) or (ticket["t"] != "mfa"):
        raise status.notAuthenticated

    # Get account
    try:
        account = accounts.get_account(ticket["u"])
    except status.resourceNotFound:
        raise status.notAuthenticated

    # Check TOTP code and complete authentication
    if not account.check_totp(body.code):
        raise status.invalidCredentials
    else:
        tickets.revoke_ticket(ticket["i"])
        security_cookie = security_cookies.decode_security_cookie(cookie=request.cookies.get("security_cookie"))
        security_cookie.add_user(account)
        session = sessions.create_user_session(account, request.ctx.device, request.ip)
        resp = json({
            "user_id": account.id,
            "access_token": session.signed_token
        })
        resp.cookies["security_cookie"] = security_cookie.signed_cookie
        return resp


@v1.post("/recovery/password")
@validate(json=PasswordRecoveryForm)
@security.v1_protected(require_auth=False, ratelimit_key="verify", ratelimit_scope="ip")  # placeholder ratelimit bucket
async def v1_password_recovery(request, body: PasswordRecoveryForm):
    # Get user ID
    user_id = accounts.get_id_from_email(body.email)

    # Get user
    user = users.get_user(user_id)

    # Create password reset ticket
    ticket = tickets.create_ticket(user, "password_reset", {
        "email": body.email
    })

    # Send password reset email
    email.send_email(body.email, user.username, "password_reset", {
        "username": user.username,
        "uri": f"https://meower.org/email?ticket={ticket}"
    })

    return HTTPResponse(status=204)

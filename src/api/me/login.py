from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field

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
    try:
        if "@" in body.username:
            user_id = accounts.get_id_from_email(body.username)
        else:
            user_id = users.get_id_from_username(body.username)
    except status.notFound:
        raise status.invalidPassword

    account = accounts.get_account(user_id)
    if not account.check_password(body.password):
        raise status.invalidPassword
    
    if account.require_mfa:
        mfa_ticket = tickets.create_ticket(account, "mfa")
        return json({
            "user_id": account.id,
            "token": None,
            "ticket": mfa_ticket,
            "mfa_required": True,
            "mfa_methods": account.mfa_methods
        })
    else:
        session = sessions.create_user_session(account, request.ctx.device, networks.get_network(request.ip))
        return json({
            "user_id": account.id,
            "token": session.signed_token,
            "ticket": None,
            "mfa_required": False,
            "mfa_methods": None
        })

@v1.post("/mfa/totp")
@validate(json=TOTPForm)
async def v1_mfa_totp(request, body: TOTPForm):
    pass

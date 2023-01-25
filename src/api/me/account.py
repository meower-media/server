from sanic import Blueprint, HTTPResponse, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from src.util import status, security
from src.entities import users, accounts, networks, sessions, tickets

v1 = Blueprint("v1_me_account", url_prefix="/account")

class UpdateEmailForm(BaseModel):
    ticket: str = Field(
        max_length=255
    )
    email: str = Field(
        max_length=255
    )

class UpdatePasswordForm(BaseModel):
    ticket: str = Field(
        max_length=255
    )
    password: str = Field(
        min_length=8,
        max_length=255
    )

class EnableTOTPForm(BaseModel):
    ticket: str = Field(
        max_length=255
    )
    secret: str = Field(
        max_length=64
    )
    code: str = Field(
        min_length=6,
        max_length=6
    )

class DisableTOTPForm(BaseModel):
    ticket: str = Field(
        max_length=255
    )

class MFARecoveryCodesForm(BaseModel):
    ticket: str = Field(
        max_length=255
    )
    regenerate: bool = Field()

@v1.get("/")
@security.sanic_protected()
async def v1_get_account(request):
    account = accounts.get_account(request.ctx.user.id)
    if account is None:
        raise status.internal
    else:
        return json(account.client)

@v1.patch("/email")
@validate(json=UpdateEmailForm)
@security.sanic_protected()
async def v1_update_email(request, body: UpdateEmailForm):
    verification_ticket = tickets.get_ticket_details(body.ticket)
    if (verification_ticket["t"] != "verification") or (verification_ticket["u"] != request.ctx.user.id):
        raise status.notAuthenticated

    account = accounts.get_account(request.ctx.user.id)
    if account is None:
        raise status.internal
    else:
        account.change_email(body.email)
    
    return HTTPResponse(staus=204)

@v1.post("/password")
@validate(json=UpdatePasswordForm)
@security.sanic_protected()
async def v1_update_password(request, body: UpdatePasswordForm):
    verification_ticket = tickets.get_ticket_details(body.ticket)
    if (verification_ticket["t"] != "verification") or (verification_ticket["u"] != request.ctx.user.id):
        raise status.notAuthenticated

    account = accounts.get_account(request.ctx.user.id)
    if account is None:
        raise status.internal
    else:
        account.change_password(body.password)
    
    return HTTPResponse(staus=204)

@v1.patch("/mfa/totp")
@validate(json=EnableTOTPForm)
@security.sanic_protected()
async def v1_mfa_enable_totp(request, body: EnableTOTPForm):
    verification_ticket = tickets.get_ticket_details(body.ticket)
    if (verification_ticket["t"] != "verification") or (verification_ticket["u"] != request.ctx.user.id):
        raise status.notAuthenticated

    account = accounts.get_account(request.ctx.user.id)
    if account is None:
        raise status.internal
    else:
        account.enable_totp(body.secret, body.code)
    
    return json({"recovery_codes": account.recovery_codes})

@v1.delete("/mfa/totp")
@validate(json=DisableTOTPForm)
@security.sanic_protected()
async def v1_mfa_disable_totp(request, body: DisableTOTPForm):
    verification_ticket = tickets.get_ticket_details(body.ticket)
    if (verification_ticket["t"] != "verification") or (verification_ticket["u"] != request.ctx.user.id):
        raise status.notAuthenticated

    account = accounts.get_account(request.ctx.user.id)
    if account is None:
        raise status.internal
    else:
        account.disable_totp()
    
    return HTTPResponse(status=204)

@v1.post("/mfa/recovery-codes")
@validate(json=MFARecoveryCodesForm)
@security.sanic_protected()
async def v1_mfa_recovery_codes(request, body: MFARecoveryCodesForm):
    verification_ticket = tickets.get_ticket_details(body.ticket)
    if (verification_ticket["t"] != "verification") or (verification_ticket["u"] != request.ctx.user.id):
        raise status.notAuthenticated

    account = accounts.get_account(request.ctx.user.id)
    if account is None:
        raise status.internal

    if body.regenerate:
        account.regenerate_recovery_codes()
    
    return json(account.recovery_codes)

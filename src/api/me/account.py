from sanic import Blueprint, HTTPResponse, json
from sanic_ext import validate
from pydantic import BaseModel, Field

from ..global_models import RequestVerification
from src.util import status, security
from src.entities import accounts, tickets

v1 = Blueprint("v1_me_account", url_prefix="/account")

class UpdateEmailForm(BaseModel):
    auth: RequestVerification = None
    email: str = Field(
        max_length=255
    )

class UpdatePasswordForm(BaseModel):
    auth: RequestVerification = None
    password: str = Field(
        min_length=8,
        max_length=255
    )

class EnableTOTPForm(BaseModel):
    auth: RequestVerification = None
    secret: str = Field(
        max_length=64
    )
    code: str = Field(
        min_length=6,
        max_length=6
    )

class DisableTOTPForm(BaseModel):
    auth: RequestVerification = None

class MFARecoveryCodesForm(BaseModel):
    auth: RequestVerification = None
    regenerate: bool = Field()

@v1.get("/")
@security.v1_protected(allow_bots=False)
async def v1_get_account(request):
    account = accounts.get_account(request.ctx.user.id)
    
    return json(account.client)

@v1.patch("/email")
@validate(json=UpdateEmailForm)
@security.v1_protected(allow_bots=False)
async def v1_update_email(request, body: UpdateEmailForm):
    account = accounts.get_account(request.ctx.user.id)
    
    account.change_email(body.email)
    
    return HTTPResponse(status=204)

@v1.post("/password")
@validate(json=UpdatePasswordForm)
@security.v1_protected(allow_bots=False)
async def v1_update_password(request, body: UpdatePasswordForm):
    account = accounts.get_account(request.ctx.user.id)
    
    account.change_password(body.password)
    
    return HTTPResponse(staus=204)

@v1.patch("/mfa/totp")
@validate(json=EnableTOTPForm)
@security.v1_protected(allow_bots=False)
async def v1_mfa_enable_totp(request, body: EnableTOTPForm):
    account = accounts.get_account(request.ctx.user.id)

    account.enable_totp(body.secret, body.code)
    
    return json({"recovery_codes": account.recovery_codes})

@v1.delete("/mfa/totp")
@validate(json=DisableTOTPForm)
@security.v1_protected(allow_bots=False)
async def v1_mfa_disable_totp(request, body: DisableTOTPForm):
    account = accounts.get_account(request.ctx.user.id)

    account.disable_totp()
    
    return HTTPResponse(status=204)

@v1.post("/mfa/recovery-codes")
@validate(json=MFARecoveryCodesForm)
@security.v1_protected(allow_bots=False)
async def v1_mfa_recovery_codes(request, body: MFARecoveryCodesForm):
    account = accounts.get_account(request.ctx.user.id)

    if body.regenerate:
        account.regenerate_recovery_codes()
    
    return json(account.recovery_codes)

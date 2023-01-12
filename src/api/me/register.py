from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional
import os

from src.util import status, security
from src.entities import accounts, networks, sessions

v1 = Blueprint("v1_me_register", url_prefix="/register")

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

@v1.post("/")
@validate(json=RegistrationForm)
async def v1_register(request, body: RegistrationForm):
    if os.getenv("CAPTCHA_PROVIDER") is not None:
        if not security.check_captcha(body.captcha, request.ip):
            raise status.invalidCaptcha

    account = accounts.create_account(body.username, body.password, body.child)
    session = sessions.create_user_session(account, request.ctx.device, networks.get_network(request.ip))
    return json({"user_id": account.id, "token": session.signed_token})

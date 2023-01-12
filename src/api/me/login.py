from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import status
from src.entities import users, accounts, networks, sessions

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

@v1.post("/password")
@validate(json=PasswordForm)
async def v1_login_password(request, body: PasswordForm):
    try:
        if "@" in body.username:
            user_id = users.get_id_from_email(body.username)
        else:
            user_id = users.get_id_from_username(body.username)
    except status.notFound:
        raise status.invalidPassword

    account = accounts.get_account(user_id)
    if not account.check_password(body.password):
        raise status.invalidPassword
    
    session = sessions.create_user_session(account, request.ctx.device, networks.get_network(request.ip))
    return json({"user_id": account.id, "token": session.signed_token})

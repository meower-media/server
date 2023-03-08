from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional
import time

from src.util import status, security
from src.entities import users, accounts, applications

v1 = Blueprint("v1_applications_migrate", url_prefix="/migrate")


class MigrationForm(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=20
    )
    password: str = Field(
        max_length=255
    )
    captcha: Optional[str] = Field(
        max_length=2048
    )


@v1.post("/")
@validate(json=MigrationForm)
@security.v1_protected(allow_bots=False, ignore_suspension=False)
async def v1_migrate_user_to_bot(request, body: MigrationForm):
    # Check whether migrations can still be completed
    if time.time() > 1688169599:
        raise status.featureDiscontinued

    # Get user ID by username
    user_id = users.get_id_from_username(body.username)

    # Make sure migrating account isn't the same as the currently authorized user
    if request.ctx.user.id == user_id:
        raise status.missingPermissions

    # Get account and check password
    account = accounts.get_account(user_id)
    if account.locked:
        raise status.accountLocked
    elif not account.check_password(body.password):
        raise status.invalidCredentials

    # Migrate user
    user = users.get_user(user_id)
    application = applications.migrate_user_to_bot(user, request.ctx.user)
    bot = application.create_bot(body.username)
    token = bot.rotate_bot_session()

    return json({
        "application": application,
        "bot": bot.client,
        "token": token
    })

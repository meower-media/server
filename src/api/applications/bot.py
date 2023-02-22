from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field

from . import get_application_or_abort_if_not_maintainer
from ..global_models import RequestVerification
from src.util import security

v1 = Blueprint("v1_applications_bot", url_prefix="/<application_id:str>/bot")


class CreateBotForm(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=20
    )


class GetBotTokenForm(BaseModel):
    auth: RequestVerification = None


@v1.get("/")
@security.sanic_protected(allow_bots=False)
async def v1_get_application_bot(request, application_id: str):
    application = get_application_or_abort_if_not_maintainer(application_id, request.ctx.user)
    return json(application.bot.client)


@v1.post("/")
@validate(json=CreateBotForm)
@security.sanic_protected(allow_bots=False, ignore_suspension=False)
async def v1_create_application_bot(request, application_id: str, body: CreateBotForm):
    application = get_application_or_abort_if_not_maintainer(application_id, request.ctx.user)
    bot = application.create_bot(body.username)
    token = bot.rotate_bot_session()
    
    return json({
        "bot": bot.client,
        "token": token
    })


@v1.post("/token")
@validate(json=GetBotTokenForm)
@security.sanic_protected(allow_bots=False, ignore_suspension=False)
async def v1_get_application_bot_token(request, application_id: str, body: GetBotTokenForm):
    # Get application
    application = get_application_or_abort_if_not_maintainer(application_id, request.ctx.user)

    # Generate new token
    token = application.bot.rotate_bot_session()

    return json({"token": token})

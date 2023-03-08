from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import security
from src.entities import chats

v1 = Blueprint("v1_me_chats", url_prefix="/chats")


class CreateChatForm(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=20
    )


@v1.get("/")
@security.v1_protected(allow_bots=False)
async def v1_get_chats(request):
    active_chats = chats.get_active_chats(request.ctx.user)
    return json([chat.public for chat in active_chats])


@v1.post("/")
@validate(json=CreateChatForm)
@security.v1_protected(ratelimit_key="open_chat", ratelimit_scope="user", allow_bots=False)
async def v1_create_chat(request, body: CreateChatForm):
    chat = chats.create_chat(body.name, request.ctx.user.id)
    return json(chat.public)

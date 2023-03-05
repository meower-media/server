from sanic import Blueprint, json

from src.util import security
from src.entities import chats

v1 = Blueprint("v1_invites", url_prefix="/invites")


@v1.get("/chats/<invite_code:str>")
@security.sanic_protected(allow_bots=False)
async def v1_get_chat_invite(request, invite_code: str):
    chat = chats.get_chat_by_invite_code(invite_code)
    return json(chat.public)


@v1.post("/chats/<invite_code:str>")
@security.sanic_protected(allow_bots=False)
async def v1_accept_chat_invite(request, invite_code: str):
    chat = chats.get_chat_by_invite_code(invite_code)
    chat.add_member(request.ctx.user)
    return json(chat.public)

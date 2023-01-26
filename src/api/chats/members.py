from sanic import Blueprint, json

from . import get_chat_or_abort_if_no_membership
from src.util import status, security
from src.entities import users

v1 = Blueprint("v1_chats_members", url_prefix="/members/<user_id:str>")

@v1.put("/")
@security.sanic_protected(ignore_suspension=False)
async def v1_add_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    chat.add_member(users.get_user(user_id))

    return json(chat.public)

@v1.delete("/")
@security.sanic_protected()
async def v1_remove_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if (request.ctx.user.id == user_id) or ((chat.permissions.get(request.ctx.user.id, 0) > 0) and (chat.permissions.get(user_id, 0) < 1)):
        chat.remove_member(users.get_user(user_id))

        return json(chat.public)
    else:
        raise status.missingPermissions

@v1.post("/promote")
@security.sanic_protected()
async def v1_promote_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if chat.permissions.get(request.ctx.user.id, 0) < 2:
        raise status.missingPermissions

    chat.promote_member(users.get_user(user_id))

    return json(chat.public)

@v1.post("/demote")
@security.sanic_protected()
async def v1_demote_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if chat.permissions.get(request.ctx.user.id, 0) < 2:
        raise status.missingPermissions

    chat.demote_member(users.get_user(user_id))

    return json(chat.public)

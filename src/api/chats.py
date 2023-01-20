from sanic import Blueprint, json, HTTPResponse
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from src.util import status, security
from src.entities import users, chats, messages

v1 = Blueprint("v1_chats", url_prefix="/chats/<chat_id:str>")

class EditChatForm(BaseModel):
    name: Optional[str] = Field(
        min_length=1,
        max_length=20
    )
    owner_id: Optional[str] = Field(
        min_length=1,
        max_length=32
    )

class NewMessageForm(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=2000
    )

def get_chat_or_abort_if_no_membership(chat_id: str, user: users.User):
    chat = chats.get_chat(chat_id)
    if (chat is None) or (not chat.has_member(user)):
        raise status.notFound
    return chat

@v1.get("/")
@security.sanic_protected()
async def v1_get_chat(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    return json(chat.public)

@v1.patch("/")
@validate(json=EditChatForm)
@security.sanic_protected(check_suspension=True)
async def v1_update_chat(request, chat_id: str, body: EditChatForm):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if body.name is not None:
        if chat.permissions.get(request.ctx.user.id, 0) < 1:
            raise status.missingPermissions

        chat.update_name(body.name)
    if body.owner_id is not None:
        if chat.permissions.get(request.ctx.user.id, 0) < 2:
            raise status.missingPermissions

        chat.transfer_ownership(users.get_user(body.owner_id))

    return json(chat.public)

@v1.delete("/")
@security.sanic_protected()
async def v1_delete_chat(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if chat.permissions.get(request.ctx.user.id, 0) < 2:
        raise status.missingPermissions

    chat.delete()

    return HTTPResponse(status=204)

@v1.put("/members/<user_id:str>")
@security.sanic_protected(check_suspension=True)
async def v1_add_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    chat.add_member(users.get_user(user_id))

    return json(chat.public)

@v1.delete("/members/<user_id:str>")
@security.sanic_protected()
async def v1_remove_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if (request.ctx.user.id == user_id) or ((chat.permissions.get(request.ctx.user.id, 0) > 0) and (chat.permissions.get(user_id, 0) < 1)):
        chat.remove_member(users.get_user(user_id))

        return json(chat.public)
    else:
        raise status.missingPermissions

@v1.post("/members/<user_id:str>/promote")
@security.sanic_protected()
async def v1_promote_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if chat.permissions.get(request.ctx.user.id, 0) < 2:
        raise status.missingPermissions

    chat.promote_member(users.get_user(user_id))

    return json(chat.public)

@v1.post("/members/<user_id:str>/demote")
@security.sanic_protected()
async def v1_demote_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if chat.permissions.get(request.ctx.user.id, 0) < 2:
        raise status.missingPermissions

    chat.demote_member(users.get_user(user_id))

    return json(chat.public)

@v1.post("/refresh-invite")
@security.sanic_protected()
async def v1_refresh_chat_invite(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)
    
    if chat.permissions.get(request.ctx.user.id, 0) < 1:
        raise status.missingPermissions

    chat.refresh_invite_code()
    
    return json(chat.public)

@v1.get("/messages")
@security.sanic_protected()
async def v1_get_chat_messages(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    fetched_messages = messages.get_latest_messages(chat, before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"messages": [message.public for message in fetched_messages]})

@v1.post("/messages")
@validate(json=NewMessageForm)
@security.sanic_protected(check_suspension=True)
async def v1_create_chat_message(request, chat_id: str, body: NewMessageForm):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    message = messages.create_message(chat, request.ctx.user, body.content)
    return json(message.public)

@v1.get("/messages/search")
@security.sanic_protected()
async def v1_search_chat_messages(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    fetched_messages = messages.search_messages(chat, request.args.get("q", ""), before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"messages": [message.public for message in fetched_messages]})

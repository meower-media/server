from sanic import Blueprint, json, HTTPResponse
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from src.util import status
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
    if user.id not in chat.member_ids:
        raise status.notFound

@v1.middleware("request")
async def check_authentication(request):
    if request.ctx.user is None:
        raise status.notAuthenticated

@v1.get("/")
async def v1_get_chat(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    return json(chat.public)

@v1.patch("/")
async def v1_update_chat(request, chat_id: str, body: EditChatForm):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if body.name is not None:
        chat.update_name(body.name)
    if body.owner_id is not None:
        chat.transfer_ownership(users.get_user(body.owner_id))

    return json(chat.public)

@v1.delete("/")
async def v1_delete_chat(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if chat.permissions.get(request.ctx.user.id, 0) < 2:
        raise status.notAuthenticated

    chat.delete()

    return HTTPResponse(status=204)

@v1.put("/members/<user_id:str>")
async def v1_add_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    chat.add_member(users.get_user(user_id))

    return json(chat.public)

@v1.delete("/members/<user_id:str>")
async def v1_remove_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if (request.ctx.user.id == user_id) or ((chat.permissions.get(request.ctx.user.id, 0) > 0) and (chat.permissions.get(user_id, 0) < 2)):
        chat.remove_member(users.get_user(user_id))

        return json(chat.public)
    else:
        pass

@v1.post("/members/<user_id:str>/promote")
async def v1_promote_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    chat.promote(users.get_user(user_id))

    return json(chat.public)

@v1.post("/members/<user_id:str>/demote")
async def v1_demote_chat_member(request, chat_id: str, user_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    chat.demote(users.get_user(user_id))

    return json(chat.public)

@v1.post("/refresh-invite")
async def v1_refresh_chat_invite(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)
    
    if chat.permissions.get(request.ctx.user.id, 0) < 1:
        raise status.notAuthenticated

    chat.refresh_invite_code()
    
    return json(chat.public)

@v1.get("/messages")
async def v1_get_chat_messages(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    messages = messages.get_messages(chat, before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"messages": messages})

@v1.post("/messages")
@validate(json=NewMessageForm)
async def v1_create_chat_message(request, chat_id: str, body: NewMessageForm):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    message = messages.create_message(chat, request.ctx.user, body.content)
    return json(message.public)

@v1.get("/messages/search")
async def v1_search_chat_messages(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    messages = messages.search_messages(chat, request.args.get("q"), before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"messages": messages})

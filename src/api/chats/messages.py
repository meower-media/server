from sanic import Blueprint, HTTPResponse, json
from sanic_ext import validate
from pydantic import BaseModel, Field

from . import get_chat_or_abort_if_no_membership
from src.util import status, security
from src.entities import messages

v1 = Blueprint("v1_chats_messages", url_prefix="/messages")

class NewMessageForm(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=2000
    )

class EditMessageForm(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=2000
    )

@v1.get("/")
@security.sanic_protected()
async def v1_get_chat_messages(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    fetched_messages = messages.get_latest_messages(chat, before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"messages": [message.public for message in fetched_messages]})

@v1.post("/")
@validate(json=NewMessageForm)
@security.sanic_protected(ignore_suspension=False)
async def v1_create_chat_message(request, chat_id: str, body: NewMessageForm):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    message = messages.create_message(chat, request.ctx.user, body.content)
    return json(message.public)

@v1.get("/<message_id:str>")
@security.sanic_protected()
async def v1_get_chat_message(request, chat_id: str, message_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    # Get message
    message = messages.get_message(message_id)
    if message.chat_id != chat.id:
        raise status.notFound
    
    return json(message.public)

@v1.patch("/<message_id:str>")
@validate(json=EditMessageForm)
@security.sanic_protected()
async def v1_edit_chat_message(request, chat_id: str, message_id: str, body: EditMessageForm):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    # Get message
    message = messages.get_message(message_id)
    if message.chat_id != chat.id:
        raise status.notFound
    
    # Edit message
    if message.author.id != request.ctx.user.id:
        raise status.missingPermissions
    else:
        message.edit(body.content)
        return json(message.public)

@v1.delete("/<message_id:str>")
@security.sanic_protected()
async def v1_delete_chat_message(request, chat_id: str, message_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    # Get message
    message = messages.get_message(message_id)
    if message.chat_id != chat.id:
        raise status.notFound
    
    # Delete message
    if (message.author.id != request.ctx.user.id) and (chat.permissions.get(request.ctx.user.id, 0) < 1):
        raise status.missingPermissions
    else:
        message.delete()
        return HTTPResponse(status=204)

@v1.get("/<message_id:str>/context")
@security.sanic_protected()
async def v1_get_chat_message_context(request, chat_id: str, message_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    fetched_messages = messages.get_message_context(chat, message_id)
    return json({"messages": [message.public for message in fetched_messages]})

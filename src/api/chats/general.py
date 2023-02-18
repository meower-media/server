from sanic import Blueprint, json, HTTPResponse
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from .util import get_chat_or_abort_if_no_membership
from src.util import status, security
from src.entities import users, messages

v1 = Blueprint("v1_chats_general", url_prefix="/")


class EditChatForm(BaseModel):
    name: Optional[str] = Field(
        min_length=1,
        max_length=20
    )
    owner_id: Optional[str] = Field(
        min_length=1,
        max_length=25
    )


@v1.get("/")
@security.sanic_protected()
async def v1_get_chat(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    return json(chat.public)


@v1.patch("/")
@validate(json=EditChatForm)
@security.sanic_protected(ratelimit="update_chat", ignore_suspension=False)
async def v1_update_chat(request, chat_id: str, body: EditChatForm):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if body.name:
        if chat.permissions.get(request.ctx.user.id, 0) < 1:
            raise status.missingPermissions

        chat.update_name(body.name)
    if body.owner_id:
        if chat.permissions.get(request.ctx.user.id, 0) < 2:
            raise status.missingPermissions

        chat.transfer_ownership(users.get_user(body.owner_id, return_deleted=False))

    return json(chat.public)


@v1.delete("/")
@security.sanic_protected(ratelimit="update_chat")
async def v1_delete_chat(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if chat.permissions.get(request.ctx.user.id, 0) < 2:
        raise status.missingPermissions

    chat.delete()

    return HTTPResponse(status=204)


@v1.post("/refresh-invite")
@security.sanic_protected(ratelimit="update_chat")
async def v1_refresh_chat_invite(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    if chat.permissions.get(request.ctx.user.id, 0) < 1:
        raise status.missingPermissions

    chat.refresh_invite_code()

    return json(chat.public)


@v1.post("/typing")
@security.sanic_protected(ratelimit="typing", ignore_suspension=False)
async def v1_chat_typing_indicator(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    chat.emit_typing(request.ctx.user)

    return HTTPResponse(status=204)


@v1.get("/search")
@security.sanic_protected(ratelimit="search")
async def v1_search_chat_messages(request, chat_id: str):
    chat = get_chat_or_abort_if_no_membership(chat_id, request.ctx.user)

    fetched_messages = messages.search_messages(chat, request.args.get("q", ""), before=request.args.get("before"),
                                                after=request.args.get("after"),
                                                limit=int(request.args.get("limit", 25)))
    return json([message.public for message in fetched_messages])

from sanic import Blueprint, json, HTTPResponse
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import status, security
from src.entities import users, chats

v0 = Blueprint("v0_users", url_prefix="/users/<username:str>")
v1 = Blueprint("v1_users", url_prefix="/users/<user_id:str>")


@v0.get("/")
async def v0_get_user(request, username: str):
    try:
        user_id = users.get_id_from_username(username)
        user = users.get_user(user_id)
    except status.resourceNotFound:
        return json({"error": True, "type": "notFound"}, status=404)
    except:
        return json({"error": True, "type": "internal"}, status=500)
    else:
        resp = user.legacy_public
        resp["error"] = False
        return json(resp)


@v1.get("/")
async def v1_get_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)

    if request.ctx.user and (request.ctx.user.id == user.id):
        return json(user.client)
    else:
        return json(user.public)


@v1.get("/following")
async def v1_get_following(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    fetched_users = user.get_following(before=request.args.get("before"),
                                            after=request.args.get("after"),
                                            limit=int(request.args.get("limit", 50)))
    return json([user.partial for user in fetched_users])


@v1.get("/followers")
async def v1_get_followers(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    fetched_users = user.get_followed(before=request.args.get("before"),
                                            after=request.args.get("after"),
                                            limit=int(request.args.get("limit", 50)))
    return json([user.partial for user in fetched_users])


@v1.post("/follow")
@security.sanic_protected(ratelimit_key="change_relationship", ratelimit_scope="user", allow_bots=False, ignore_suspension=False)
async def v1_follow_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    request.ctx.user.follow_user(user)

    return HTTPResponse(status=204)


@v1.post("/unfollow")
@security.sanic_protected(ratelimit_key="change_relationship", ratelimit_scope="user", allow_bots=False)
async def v1_unfollow_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    request.ctx.user.unfollow_user(user)

    return HTTPResponse(status=204)


@v1.post("/block")
@security.sanic_protected(ratelimit_key="change_relationship", ratelimit_scope="user", allow_bots=False)
async def v1_block_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    request.ctx.user.block_user(user)

    return HTTPResponse(status=204)


@v1.post("/unblock")
@security.sanic_protected(ratelimit_key="change_relationship", ratelimit_scope="user", allow_bots=False)
async def v1_unblock_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    request.ctx.user.unblock_user(user)

    return HTTPResponse(status=204)


@v1.get("/dm")
@security.sanic_protected(ratelimit_key="open_chat", ratelimit_scope="user")
async def v1_dm_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    chat = chats.get_dm_chat(request.ctx.user, user)

    return json(chat.public)

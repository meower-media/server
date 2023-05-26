from sanic import Blueprint, json, HTTPResponse
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import status, security
from src.entities import users, posts, chats
from src.database import db

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
        return json({"error": True, "type": "Internal"}, status=500)
    else:
        resp = user.legacy_public
        resp["is_legacy_pfp"] = True
        resp["error"] = False
        return json(resp)


@v0.get("/posts")
async def v0_get_user_posts(request, username: str):
    # Get page
    page = request.args.get("page", 1)
    try:
        page = int(page)
    except:
        return json({"error": True, "type": "Datatype"}, status=500)
    else:
        if page < 1:
            page = 1

    # Get user posts
    try:
        user_id = users.get_id_from_username(username)
        fetched_posts = posts.get_user_posts(user_id, skip=((page-1)*25))
    except status.resourceNotFound:
        fetched_posts = []
    except:
        return json({"error": True, "type": "Internal"}, status=500)
    
    # Return posts
    return json({
        "error": False,
        "autoget": [post.legacy_public for post in fetched_posts],
        "page#": page,
        "pages": ((db.posts.count_documents({"deleted_at": None, "author_id": user_id}) // 25)+1)
    })


@v1.get("/")
async def v1_get_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)

    if request.ctx.user and (request.ctx.user.id == user.id):
        data = user.client
        data["is_legacy_pfp"] = False
        return json(data)
    else:
        data = user.public
        data["is_legacy_pfp"] = False
        return json(data)


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
@security.v1_protected(ratelimit_key="change_relationship", ratelimit_scope="user", allow_bots=False, ignore_suspension=False)
async def v1_follow_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    request.ctx.user.follow_user(user)

    return HTTPResponse(status=204)


@v1.post("/unfollow")
@security.v1_protected(ratelimit_key="change_relationship", ratelimit_scope="user", allow_bots=False)
async def v1_unfollow_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    request.ctx.user.unfollow_user(user)

    return HTTPResponse(status=204)


@v1.post("/block")
@security.v1_protected(ratelimit_key="change_relationship", ratelimit_scope="user", allow_bots=False)
async def v1_block_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    request.ctx.user.block_user(user)

    return HTTPResponse(status=204)


@v1.post("/unblock")
@security.v1_protected(ratelimit_key="change_relationship", ratelimit_scope="user", allow_bots=False)
async def v1_unblock_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    request.ctx.user.unblock_user(user)

    return HTTPResponse(status=204)


@v1.get("/dm")
@security.v1_protected(ratelimit_key="open_chat", ratelimit_scope="user")
async def v1_dm_user(request, user_id: str):
    user = users.get_user(user_id, return_deleted=False)
    chat = chats.get_dm_chat(request.ctx.user, user)

    return json(chat.public)

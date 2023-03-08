from sanic import Blueprint, json, HTTPResponse
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from .global_models import AuthorMasquerade
from src.util import status, security
from src.entities import posts, comments, chats, messages
from src.database import db

v0 = Blueprint("v0_posts", url_prefix="/posts")
v1 = Blueprint("v1_posts", url_prefix="/posts/<post_id:str>")


class PostEditForm(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000
    )


class CommentCreateForm(BaseModel):
    masquerade: Optional[dict] = Field()
    bridged: Optional[bool] = Field()
    content: str = Field(
        min_length=1,
        max_length=2000
    )


class CommentEditForm(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000
    )


@v0.get("/")
async def v0_get_post(request):
    # Get post ID
    post_id = request.args.get("id")
    if not post_id:
        return json({"error": True, "type": "noQueryString"}, status=400)

    # Get and return post
    try:
        post = posts.get_post(post_id)
    except status.resourceNotFound:
        return json({"error": True, "type": "notFound"}, status=404)
    except:
        return json({"error": True, "type": "internal"}, status=500)
    else:
        resp = post.legacy_public
        resp["error"] = False
        return json(resp)


@v0.get("/<chat_id:str>")
@security.v0_protected()
async def v0_get_chat_messages(request, chat_id: str):
    # Get chat
    try:
        chat = chats.get_chat(chat_id)
    except status.resourceNotFound:
        return json({"error": True, "type": "notFound"}, status=404)

    # Check if authorized user is in chat
    if not chat.has_member(request.ctx.user):
        return json({"error": True, "type": "notFound"}, status=404)
    
    # Extract page
    page = int(request.args.get("page", 1))
    if page < 1:
        page = 1

    # Fetch and return chat messages
    fetched_messages = messages.get_latest_messages(chat, skip=((page-1)*25), limit=25)
    return json({
        "error": False,
        "autoget": [message.legacy_public for message in fetched_messages],
        "page#": page,
        "pages": ((db.messages.count_documents({"chat_id": chat.id, "deleted_at": None}) // 25)+1)
    })

@v1.get("/")
async def v1_get_post(request, post_id: str):
    post = posts.get_post(post_id)
    return json(post.public)


@v1.patch("/")
@validate(json=PostEditForm)
@security.v1_protected(ratelimit_key="edit_post", ratelimit_scope="user", ignore_suspension=False)
async def v1_edit_post(request, post_id: str, body: PostEditForm):
    post = posts.get_post(post_id)
    if post.author.id == request.ctx.user.id:
        post.edit(request.ctx.user, body.content)
        return json(post.public)
    else:
        raise status.missingPermissions


@v1.delete("/")
@security.v1_protected()
async def v1_delete_post(request, post_id: str):
    post = posts.get_post(post_id)
    if post.author.id == request.ctx.user.id:
        post.delete()
        return HTTPResponse(status=204)
    else:
        raise status.missingPermissions


@v1.get("/status")
@security.v1_protected(allow_bots=False)
async def v1_post_status(request, post_id: str):
    post = posts.get_post(post_id)
    return json({
        "liked": post.liked(request.ctx.user),
        "meowed": post.meowed(request.ctx.user)
    })


@v1.post("/like")
@security.v1_protected(ratelimit_key="reputation", ratelimit_scope="user", allow_bots=False, ignore_suspension=False)
async def v1_like_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.like(request.ctx.user)
    return HTTPResponse(status=204)


@v1.post("/unlike")
@security.v1_protected(ratelimit_key="reputation", ratelimit_scope="user", allow_bots=False, ignore_suspension=False)
async def v1_unlike_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.unlike(request.ctx.user)
    return HTTPResponse(status=204)


@v1.post("/meow")
@security.v1_protected(ratelimit_key="reputation", ratelimit_scope="user", allow_bots=False, ignore_suspension=False)
async def v1_meow_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.meow(request.ctx.user)
    return HTTPResponse(status=204)


@v1.post("/unmeow")
@security.v1_protected(ratelimit_key="reputation", ratelimit_scope="user", allow_bots=False, ignore_suspension=False)
async def v1_unmeow_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.unmeow(request.ctx.user)
    return HTTPResponse(status=204)


@v1.get("/comments")
async def v1_get_comments(request, post_id: str):
    post = posts.get_post(post_id)
    fetched_comments = comments.get_post_comments(post, before=request.args.get("before"),
                                                  after=request.args.get("after"),
                                                  limit=int(request.args.get("limit", 25)))
    return json([comment.public for comment in fetched_comments])


@v1.post("/comments")
@validate(json=CommentCreateForm)
@security.v1_protected(ratelimit_key="create_comment", ratelimit_scope="user", ignore_suspension=False)
async def v1_create_comment(request, post_id: str, body: CommentCreateForm):
    if body.masquerade:
        AuthorMasquerade(**body.masquerade)

    post = posts.get_post(post_id)
    comment = comments.create_comment(post, request.ctx.user, body.content, masquerade=body.masquerade, bridged=body.bridged)
    return json(comment.public)


@v1.get("/comments/<comment_id:str>")
async def v1_get_comment(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    return json(comment.public)


@v1.patch("/comments/<comment_id:str>")
@validate(json=CommentEditForm)
@security.v1_protected(ratelimit_key="edit_comment", ratelimit_scope="user", ignore_suspension=False)
async def v1_edit_comment(request, post_id: str, comment_id: str, body: CommentEditForm):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    if comment.author.id == request.ctx.user.id:
        comment.edit(request.ctx.user, body.content)
        return json(comment.public)
    else:
        raise status.missingPermissions


@v1.delete("/comments/<comment_id:str>")
@security.v1_protected()
async def v1_delete_comment(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    if comment.author.id == request.ctx.user.id:
        comment.delete()
        return HTTPResponse(status=204)
    else:
        raise status.missingPermissions


@v1.get("/comments/<comment_id:str>/status")
@security.v1_protected(allow_bots=False)
async def v1_comment_status(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    return json({
        "liked": comment.liked(request.ctx.user)
    })


@v1.post("/comments/<comment_id:str>/like")
@security.v1_protected(ratelimit_key="reputation", ratelimit_scope="user", allow_bots=False, ignore_suspension=False)
async def v1_like_comment(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    comment.like(request.ctx.user)
    return HTTPResponse(status=204)


@v1.post("/comments/<comment_id:str>/unlike")
@security.v1_protected(ratelimit_key="reputation", ratelimit_scope="user", allow_bots=False, ignore_suspension=False)
async def v1_unlike_comment(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    comment.unlike(request.ctx.user)
    return HTTPResponse(status=204)


@v1.get("/comments/<comment_id:str>/replies")
async def v1_get_comment_replies(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    fetched_replies = comments.get_comment_replies(comment, before=request.args.get("before"),
                                                   after=request.args.get("after"),
                                                   limit=int(request.args.get("limit", 25)))
    return json([reply.public for reply in fetched_replies])


@v1.post("/comments/<comment_id:str>/replies")
@validate(json=CommentCreateForm)
@security.v1_protected(ratelimit_key="create_comment", ratelimit_scope="user", ignore_suspension=False)
async def v1_create_comment_reply(request, post_id: str, comment_id: str, body: CommentCreateForm):
    if body.masquerade:
        AuthorMasquerade(**body.masquerade)

    post = posts.get_post(post_id)
    parent_comment = comments.get_comment(comment_id)
    comment = comments.create_comment(post, request.ctx.user, body.content, parent=parent_comment, masquerade=body.masquerade, bridged=body.bridged)
    return json(comment.public)

from sanic import Blueprint, json, HTTPResponse
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from src.util import status, security
from src.entities import posts, comments

v0 = Blueprint("v0_posts", url_prefix="/posts")
v1 = Blueprint("v1_posts", url_prefix="/posts/<post_id:str>")

class PostEditForm(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000
    )

class CommentCreateForm(BaseModel):
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
    if post_id is None:
        return json({"error": True, "type": "noQueryString"}, status=400)
    
    # Get and return post
    try:
        post = posts.get_post(post_id)
    except status.notFound:
        return json({"error": True, "type": "notFound"}, status=404)
    except:
        return json({"error": True, "type": "internal"}, status=500)
    else:
        resp = post.legacy
        resp["error"] = False
        return json(resp)

@v1.get("/")
async def v1_get_post(request, post_id: str):
    post = posts.get_post(post_id)
    return json(post.public)

@v1.patch("/")
@validate(json=PostEditForm)
@security.sanic_protected(ratelimit="edit_post", ignore_suspension=False)
async def v1_edit_post(request, post_id: str, body: PostEditForm):    
    post = posts.get_post(post_id)
    if post.author.id == request.ctx.user.id:
        post.edit(request.ctx.user, body.content)
        return json(post.public)
    else:
        raise status.missingPermissions

@v1.delete("/")
@security.sanic_protected()
async def v1_delete_post(request, post_id: str):
    post = posts.get_post(post_id)
    if post.author.id == request.ctx.user.id:
        post.delete()
        return HTTPResponse(status=204)
    else:
        raise status.missingPermissions

@v1.get("/status")
@security.sanic_protected(allow_bots=False)
async def v1_post_status(request, post_id: str):
    post = posts.get_post(post_id)
    return json({
        "liked": post.liked(request.ctx.user),
        "meowed": post.meowed(request.ctx.user)
    })

@v1.post("/like")
@security.sanic_protected(ratelimit="reputation", allow_bots=False, ignore_suspension=False)
async def v1_like_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.like(request.ctx.user)
    return HTTPResponse(status=204)

@v1.post("/unlike")
@security.sanic_protected(ratelimit="reputation", allow_bots=False, ignore_suspension=False)
async def v1_unlike_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.unlike(request.ctx.user)
    return HTTPResponse(status=204)

@v1.post("/meow")
@security.sanic_protected(ratelimit="reputation", allow_bots=False, ignore_suspension=False)
async def v1_meow_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.meow(request.ctx.user)
    return HTTPResponse(status=204)

@v1.post("/unmeow")
@security.sanic_protected(ratelimit="reputation", allow_bots=False, ignore_suspension=False)
async def v1_unmeow_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.unmeow(request.ctx.user)
    return HTTPResponse(status=204)

@v1.get("/comments")
async def v1_get_comments(request, post_id: str):
    post = posts.get_post(post_id)
    fetched_comments = comments.get_post_comments(post, before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"comments": [comment.public for comment in fetched_comments]})

@v1.post("/comments")
@validate(json=CommentCreateForm)
@security.sanic_protected(ratelimit="create_comment", ignore_suspension=False)
async def v1_create_comment(request, post_id: str, body: CommentCreateForm):
    post = posts.get_post(post_id)
    comment = comments.create_comment(post, request.ctx.user, body.content)
    return json(comment.public)

@v1.get("/comments/<comment_id:str>")
async def v1_get_comment(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    return json(comment.public)

@v1.patch("/comments/<comment_id:str>")
@validate(json=CommentEditForm)
@security.sanic_protected(ratelimit="edit_comment", ignore_suspension=False)
async def v1_edit_comment(request, post_id: str, comment_id: str, body: CommentEditForm):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    if comment.author.id == request.ctx.user.id:
        comment.edit(request.ctx.user, body.content)
        return json(comment.public)
    else:
        raise status.missingPermissions

@v1.delete("/comments/<comment_id:str>")
@security.sanic_protected()
async def v1_delete_comment(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    if comment.author.id == request.ctx.user.id:
        comment.delete()
        return HTTPResponse(status=204)
    else:
        raise status.missingPermissions

@v1.get("/comments/<comment_id:str>/status")
@security.sanic_protected(allow_bots=False)
async def v1_comment_status(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    return json({
        "liked": comment.liked(request.ctx.user)
    })

@v1.post("/comments/<comment_id:str>/like")
@security.sanic_protected(ratelimit="reputation", allow_bots=False, ignore_suspension=False)
async def v1_like_comment(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    comment.like(request.ctx.user)
    return HTTPResponse(status=204)

@v1.post("/comments/<comment_id:str>/unlike")
@security.sanic_protected(ratelimit="reputation", allow_bots=False, ignore_suspension=False)
async def v1_unlike_comment(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    comment.unlike(request.ctx.user)
    return HTTPResponse(status=204)

@v1.get("/comments/<comment_id:str>/replies")
async def v1_get_comment_replies(request, post_id: str, comment_id: str):
    post = posts.get_post(post_id)
    comment = comments.get_comment(comment_id)
    fetched_replies = comments.get_comment_replies(comment, before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"replies": [reply.public for reply in fetched_replies]})

@v1.post("/comments/<comment_id:str>/replies")
@validate(json=CommentCreateForm)
@security.sanic_protected(ratelimit="create_comment", ignore_suspension=False)
async def v1_create_comment_reply(request, post_id: str, comment_id: str, body: CommentCreateForm):
    post = posts.get_post(post_id)
    parent_comment = comments.get_comment(comment_id)
    comment = comments.create_comment(post, request.ctx.user, body.content, parent=parent_comment)
    return json(comment.public)

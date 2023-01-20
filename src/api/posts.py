from sanic import Blueprint, json, HTTPResponse
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import status, security
from src.entities import posts

v0 = Blueprint("v0_posts", url_prefix="/posts")
v1 = Blueprint("v1_posts", url_prefix="/posts/<post_id:str>")

class EditForm(BaseModel):
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
@validate(json=EditForm)
@security.sanic_protected(check_suspension=True)
async def v1_edit_post(request, post_id: str, body: EditForm):    
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
@security.sanic_protected()
async def v1_post_status(request, post_id: str):
    post = posts.get_post(post_id)
    return json({
        "liked": post.liked(request.ctx.user),
        "meowed": post.meowed(request.ctx.user)
    })

@v1.post("/like")
@security.sanic_protected(check_suspension=True)
async def v1_like_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.like(request.ctx.user)
    return HTTPResponse(status=204)

@v1.post("/unlike")
@security.sanic_protected(check_suspension=True)
async def v1_unlike_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.unlike(request.ctx.user)
    return HTTPResponse(status=204)

@v1.post("/meow")
@security.sanic_protected(check_suspension=True)
async def v1_meow_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.meow(request.ctx.user)
    return HTTPResponse(status=204)

@v1.post("/unmeow")
@security.sanic_protected(check_suspension=True)
async def v1_unmeow_post(request, post_id: str):
    post = posts.get_post(post_id)
    post.unmeow(request.ctx.user)
    return HTTPResponse(status=204)

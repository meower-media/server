from sanic import Blueprint, json, HTTPResponse
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import status
from src.entities import posts

v1 = Blueprint("v1_posts", url_prefix="/posts/<post_id:str>")

class EditForm(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000
    )

@v1.get("/")
async def v1_get_post(request, post_id: str):
    post = posts.get_post(post_id)
    return json(post.public)

@v1.patch("/")
@validate(json=EditForm)
async def v1_edit_post(request, post_id: str, body: EditForm):
    if request.ctx.user is None:
        raise status.notAuthenticated
    
    post = posts.get_post(post_id)
    if post.author.id == request.ctx.user.id:
        if body.content != post.content:
            post.edit(body.content, request.ctx.user)
        return json(post.public)
    else:
        return status.notAuthenticated

@v1.delete("/")
async def v1_delete_post(request, post_id: str):
    if request.ctx.user is None:
        raise status.notAuthenticated

    post = posts.get_post(post_id)
    if post.author.id == request.ctx.user.id:
        post.delete()
        return HTTPResponse(status=204)
    else:
        return status.notAuthenticated

@v1.get("/status")
async def v1_post_status(request, post_id: str):
    if request.ctx.user is None:
        raise status.notAuthenticated

    post = posts.get_post(post_id)
    return json({
        "liked": post.liked(request.ctx.user),
        "meowed": post.meowed(request.ctx.user)
    })

@v1.post("/like")
async def v1_like_post(request, post_id: str):
    if request.ctx.user is None:
        raise status.notAuthenticated

    post = posts.get_post(post_id)
    post.like(request.ctx.user)
    return HTTPResponse(status=204)

@v1.delete("/like")
async def v1_unlike_post(request, post_id: str):
    if request.ctx.user is None:
        raise status.notAuthenticated

    post = posts.get_post(post_id)
    post.unlike(request.ctx.user)
    return HTTPResponse(status=204)

@v1.post("/meow")
async def v1_meow_post(request, post_id: str):
    if request.ctx.user is None:
        raise status.notAuthenticated

    post = posts.get_post(post_id)
    post.meow(request.ctx.user)
    return HTTPResponse(status=204)

@v1.delete("/meow")
async def v1_unmeow_post(request, post_id: str):
    if request.ctx.user is None:
        raise status.notAuthenticated

    post = posts.get_post(post_id)
    post.unmeow(request.ctx.user)
    return HTTPResponse(status=204)

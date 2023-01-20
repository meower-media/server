from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import status, security
from src.entities import posts

v0 = Blueprint("v0_home", url_prefix="/home")
v1 = Blueprint("v1_home", url_prefix="/home")

class NewPostForm(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000
    )

@v0.get("/")
async def v0_get_home(request):
    fetched_posts = posts.get_latest_posts()
    return json({
        "error": False,
        "autoget": [post.legacy for post in fetched_posts],
        "page#": 1,
        "pages": 1
    })

@v1.get("/")
@security.sanic_protected()
async def v1_get_feed(request):    
    fetched_posts = posts.get_feed(request.ctx.user, before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"posts": [post.public for post in fetched_posts]})

@v1.get("/latest")
async def v1_get_latest_posts(request):
    fetched_posts = posts.get_latest_posts(before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"posts": [post.public for post in fetched_posts]})

@v1.get("/trending")
async def v1_get_trending_posts(request):
    fetched_posts = posts.get_top_posts(before=request.args.get("before"), after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json({"posts": [post.public for post in fetched_posts]})

@v1.post("/")
@validate(json=NewPostForm)
@security.sanic_protected(check_suspension=True)
async def v1_create_post(request, body: NewPostForm):
    post = posts.create_post(request.ctx.user, body.content)
    return json(post.public)

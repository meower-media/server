from quart import Blueprint, current_app as app, request, abort
from pydantic import BaseModel, Field
import pymongo

from security import Restrictions


home_bp = Blueprint("home_bp", __name__, url_prefix="/home")


class PostBody(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


@home_bp.get("/")
async def get_home_posts():
    # Get page
    page = 1
    if request.user:
        try:
            page = int(request.args["page"])
        except: pass

    # Get posts
    query = {"post_origin": "home", "isDeleted": False}
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": (app.files.get_total_pages("posts", query) if request.user else 1)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@home_bp.post("/")
async def create_home_post():
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"post:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"post:{request.user}", 6, 5)

    # Check restrictions
    if app.security.is_restricted(request.user, Restrictions.HOME_POSTS):
        return {"error": True, "type": "accountBanned"}, 403

    # Get body
    try:
        body = PostBody(**await request.json)
    except: abort(400)

    # Create post
    FileWrite, post = app.supporter.createPost("home", request.user, body.content)
    if not FileWrite:
        abort(500)

    # Return new post
    return post, 200

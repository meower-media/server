from quart import Blueprint, current_app as app, request, abort
from quart_schema import validate_querystring, validate_request
from pydantic import BaseModel, Field
from typing import Optional
import pymongo

import security
from database import db, get_total_pages
from uploads import claim_file
from utils import log


home_bp = Blueprint("home_bp", __name__, url_prefix="/home")


class GetHomeQueryArgs(BaseModel):
    page: Optional[int] = Field(default=1, ge=1)

class PostBody(BaseModel):
    content: Optional[str] = Field(default="", max_length=4000)
    nonce: Optional[str] = Field(default=None, max_length=64)
    attachments: Optional[list[str]] = Field(default_factory=list)

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


@home_bp.get("/")
@validate_querystring(GetHomeQueryArgs)
async def get_home_posts(query_args: GetHomeQueryArgs):
    # Get posts
    query = {"post_origin": "home", "isDeleted": False}
    posts = list(db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(query_args.page-1)*25, limit=25))

    # Return posts
    return {
        "error": False,
        "autoget": posts,
        "page#": query_args.page,
        "pages": (get_total_pages("posts", query) if request.user else 1)
    }, 200


@home_bp.post("/")
@validate_request(PostBody)
async def create_home_post(data: PostBody):
    # Check authorization
    if not request.user:
        abort(401)

    if not (request.flags & security.UserFlags.POST_RATELIMIT_BYPASS):
        # Check ratelimit
        if security.ratelimited(f"post:{request.user}"):
            abort(429)

        # Ratelimit
        security.ratelimit(f"post:{request.user}", 6, 5)

    # Check restrictions
    if security.is_restricted(request.user, security.Restrictions.HOME_POSTS):
        return {"error": True, "type": "accountBanned"}, 403

    # Make sure there's not too many attachments
    if len(data.attachments) > 10:
        return {"error": True, "type": "tooManyAttachments"}, 400

    # Claim attachments
    attachments = []
    for attachment_id in set(data.attachments):
        try:
            attachments.append(claim_file(attachment_id, "attachments"))
        except Exception as e:
            log(f"Unable to claim attachment: {e}")
            return {"error": True, "type": "unableToClaimAttachment"}, 500

    # Make sure the post has text content or at least 1 attachment
    if not data.content and not attachments:
        abort(400)

    # Create post
    post = app.supporter.create_post(
        "home",
        request.user,
        data.content,
        attachments=attachments,
        nonce=data.nonce
    )

    # Return new post
    post["error"] = False
    return post, 200


@home_bp.post("/typing")
async def emit_typing():
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"typing:{request.user}"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"typing:{request.user}", 6, 5)

    # Check restrictions
    if security.is_restricted(request.user, security.Restrictions.HOME_POSTS):
        return {"error": True, "type": "accountBanned"}, 403

    # Send new state
    app.cl.broadcast({
        "chatid": "livechat",
        "u": request.user,
        "state": 101
    }, direct_wrap=True)

    return {"error": False}, 200

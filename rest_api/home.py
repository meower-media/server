from quart import Blueprint, current_app as app, abort
from quart_schema import validate_querystring, validate_request, validate_response
from pydantic import BaseModel, Field
from typing import Optional, Literal

import models
from entities import posts
from uploads import claim_file
from utils import log
from bitfield import UserBanRestrictions
from .utils import check_auth, auto_ratelimit


home_bp = Blueprint("home_bp", __name__, url_prefix="/home")


class GetHomeQueryArgs(BaseModel):
    before: Optional[int] = Field(default=None)
    after: Optional[int] = Field(default=None)
    around: Optional[int] = Field(default=None)
    page: Optional[int] = Field(default=1, ge=1)

class GetHomeResp(BaseModel):
    error: Literal[False] = Field(default=False)
    autoget: list[models.v0.Post] = Field()
    page: int = Field(alias="page#")
    pages: int = Field()

    class Config:
        by_alias = True

class PostBody(BaseModel):
    content: Optional[str] = Field(default="", max_length=4000)
    attachments: Optional[list[str]] = Field(default_factory=list)
    nonce: Optional[str] = Field(default=None, max_length=64)

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


@home_bp.get("/")
@validate_querystring(GetHomeQueryArgs)
@validate_response(GetHomeResp)
async def get_home_posts(query_args: GetHomeQueryArgs):
    return GetHomeResp(
        autoget=[posts.db_to_v0(post) for post in posts.get_latest_posts(
            "home",
            before=query_args.before,
            after=query_args.after,
            skip=(query_args.page-1)*25,
        )] if query_args.around is None else [
            posts.db_to_v0(post) for post in
            posts.get_context("home", query_args.around)
        ],
        page=query_args.page,
        pages=query_args.page+1
    ).model_dump(by_alias=True), 200

@home_bp.post("/")
@validate_request(PostBody)
@check_auth(check_restrictions=UserBanRestrictions.HOME_POSTS)
@auto_ratelimit("post", "user", 5, 5)
async def create_home_post(data: PostBody, requester: models.db.User):
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
    post = posts.create_post(
        requester["_id"],
        "home",
        data.content,
        attachments=attachments,
        nonce=data.nonce,
    )

    return {"error": False, **posts.db_to_v0(post)}, 200

@home_bp.post("/typing")
@check_auth(check_restrictions=UserBanRestrictions.HOME_POSTS)
@auto_ratelimit("typing", "user", 5, 5)
async def emit_typing(requester: models.db.User):
    app.cl.broadcast({
        "chatid": "livechat",
        "u": requester["username"],
        "state": 101
    }, direct_wrap=True)
    return {"error": False}, 200

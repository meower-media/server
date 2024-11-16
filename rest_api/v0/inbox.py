from quart import Blueprint, request, abort, current_app as app
from quart_schema import validate_querystring
from pydantic import BaseModel, Field
from typing import Optional
import pymongo

from database import db, get_total_pages


inbox_bp = Blueprint("inbox_bp", __name__, url_prefix="/inbox")


class GetInboxQueryArgs(BaseModel):
    page: Optional[int] = Field(default=1, ge=1)


@inbox_bp.get("/")
@validate_querystring(GetInboxQueryArgs)
async def get_inbox_posts(query_args: GetInboxQueryArgs):
    # Check authorization
    if not request.user:
        abort(401)

    # Get and return posts
    query = {"u": {"$or": [request.user, "Server"]}, "post_origin": "inbox", "isDeleted": False}
    return {
        "error": False,
        "autoget": app.supporter.parse_posts_v0(db.posts.find(
            query,
            sort=[("t.e", pymongo.DESCENDING)],
            skip=(query_args.page-1)*25,
            limit=25
        ), requester=request.user),
        "page#": query_args.page,
        "pages": (get_total_pages("posts", query) if request.user else 1)
    }, 200
from quart import Blueprint, request, abort
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

    # Get posts
    query = {"post_origin": "inbox", "isDeleted": False, "$or": [{"u": request.user}, {"u": "Server"}]}
    posts = list(db.posts.find(query, sort=[
        ("t.e", pymongo.DESCENDING)
    ], skip=(query_args.page-1)*25, limit=25))

    # Return posts
    return {
        "error": False,
        "autoget": posts,
        "page#": query_args.page,
        "pages": get_total_pages("posts", query)
    }, 200

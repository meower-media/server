import time, pymongo
from typing import Literal, Optional
from datetime import datetime

import models
from entities import users
from . import ids
from database import db


def db_to_v0(post: models.db.Post) -> models.v0.Post:
    author = users.get_min_user(post["author_id"])
    dt = datetime.fromtimestamp(post["created_at"])
    return {
        "_id": str(post["_id"]),
        "post_id": str(post["_id"]),
        "author": users.min_db_to_v0(author),
        "u": author["username"],
        "post_origin": post["origin"],
        "p": post["content"],
        "attachments": post["attachments"],
        "t": {
            "d": dt.strftime("%d"),
            "mo": dt.strftime("%m"),
            "y": dt.strftime("%Y"),
            "h": dt.strftime("%H"),
            "mi": dt.strftime("%M"),
            "s": dt.strftime("%S"),
            "e": post["created_at"]
        },
        "edited_at": post.get("edited_at"),
        "pinned": post.get("pinned", False),
        "isDeleted": post.get("censored", False)
    }

def create_post(
    author_id: int,
    origin: Literal["home", "livechat", "inbox"]|int,
    content: str = "",
    attachments: list[models.db.Attachment] = [],
    nonce: Optional[str] = None
) -> models.db.Post:
    _post: models.db.Post = {
        "_id": ids.gen_id(),
        "author_id": author_id,
        "origin": origin,
        "content": content,
        "attachments": attachments,
        "created_at": int(time.time())
    }
    if origin != "livechat":
        db.posts.insert_one(_post)
    return _post

def get_latest_posts(
    origin: Literal["home", "inbox"]|int,
    before: Optional[int] = None,
    after: Optional[int] = None,
    skip: int = 0,
    limit: int = 25,
    include_censored: bool = False
) -> list[models.db.Post]:
    query = {"origin": origin}

    if not include_censored:
        query["censored"] = {"$ne": True}

    if before or after:
        query["_id"] = {}
        if before:
            query["_id"]["$lt"] = before
        if after:
            query["_id"]["$gt"] = after
        
    return list(db.posts.find(
        query,
        skip=skip,
        limit=limit,
        sort=[("created_at", pymongo.DESCENDING)],
    ))

def get_context(
    origin: Literal["home", "inbox"]|int,
    id: int,
    limit: int = 25,
    include_censored: bool = False
) -> list[models.db.Post]:
    query_1 = {"origin": origin}
    query_2 = {"origin": origin}
    if not include_censored:
        query_1["censored"] = {"$ne": True}
        query_2["censored"] = {"$ne": True}
    query_1["_id"] = {"$lte": id}
    query_2["_id"] = {"$gt": id}
        
    return list(db.posts.find(
        query_1,
        limit=limit // 2,
        sort=[("created_at", pymongo.DESCENDING)],
    )) + list(db.posts.find(
        query_2,
        limit=limit // 2,
        sort=[("created_at", pymongo.DESCENDING)],
    ))

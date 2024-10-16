from quart import Blueprint, current_app as app, request, abort
from quart_schema import validate_querystring
from pydantic import BaseModel, Field
from typing import Optional
import pymongo, time, emoji

import security
from database import db, get_total_pages


posts_bp = Blueprint("posts_bp", __name__, url_prefix="/posts")


class PagedQueryArgs(BaseModel):
    page: Optional[int] = Field(default=1, ge=1)


@posts_bp.get("/<post_id>/reactions/<emoji_reaction>")
@validate_querystring(PagedQueryArgs)
async def get_post_reactors(query_args: PagedQueryArgs, post_id: str, emoji_reaction: str):
    # Get necessary post details and check access
    post = db.posts.find_one({
        "_id": post_id,
        "isDeleted": {"$ne": True}
    }, projection={"_id": 1, "post_origin": 1, "u": 1})
    if not post:
        abort(404)
    elif post["post_origin"] != "home" and not request.user:
        abort(404)
    elif post["post_origin"] == "inbox" and post["u"] not in ["Server", request.user]:
        abort(404)
    elif post["post_origin"] not in ["home", "inbox"]:
        if not db.chats.count_documents({
            "_id": post["post_origin"],
            "members": request.user,
            "deleted": False
        }, limit=1):
            abort(404)

    # Get and return reactors
    query = {"_id.post_id": post_id, "_id.emoji": emoji_reaction}
    return {
        "error": False,
        "autoget": [security.get_account(r["_id"]["user"]) for r in db.post_reactions.find(
            query,
            sort=[("time", pymongo.DESCENDING)],
            skip=(query_args.page-1)*25,
            limit=25
        )],
        "page#": query_args.page,
        "pages": (get_total_pages("post_reactions", query) if request.user else 1)
    }, 200

@posts_bp.post("/<post_id>/reactions/<emoji_reaction>")
async def add_post_reaction(post_id: str, emoji_reaction: str):
    # Check authorization
    if not request.user:
        abort(401)

    # Ratelimit
    if security.ratelimited(f"react:{request.user}"):
        abort(429)
    security.ratelimit(f"react:{request.user}", 5, 5)

    # Check if the emoji is only one emoji, with support for variants
    if not (emoji.purely_emoji(emoji_reaction) and len(emoji.distinct_emoji_list(emoji_reaction)) == 1):
        # Check if the emoji is a custom emoji
        if not db.chat_emojis.count_documents({"_id": emoji_reaction}, limit=1):
            abort(400)

    # Get necessary post details and check access
    post = db.posts.find_one({
        "_id": post_id,
        "isDeleted": {"$ne": True}
    }, projection={
        "_id": 1,
        "post_origin": 1,
        "u": 1,
        "reactions": 1
    })
    if not post:
        abort(404)
    elif post["post_origin"] == "inbox" and post["u"] not in ["Server", request.user]:
        abort(404)
    elif post["post_origin"] not in ["home", "inbox"]:
        if not db.chats.count_documents({
            "_id": post["post_origin"],
            "members": request.user,
            "deleted": False
        }, limit=1):
            abort(404)

    # Make sure there's not too many reactions (50)
    if len(post["reactions"]) >= 50:
        return {"error": True, "type": "tooManyReactions"}, 403

    # Add reaction
    db.post_reactions.update_one({"_id": {
        "post_id": post["_id"],
        "emoji": emoji_reaction,
        "user": request.user
    }}, {"$set": {"time": int(time.time())}}, upsert=True)

    # Update post
    existing_reaction = None
    for reaction in post["reactions"]:
        if reaction["emoji"] == emoji_reaction:
            existing_reaction = reaction
            break
    if existing_reaction:
        existing_reaction["count"] = db.post_reactions.count_documents({
            "_id.post_id": post["_id"],
            "_id.emoji": reaction["emoji"]
        })
    else:
        post["reactions"].append({
            "emoji": emoji_reaction,
            "count": 1
        })
    db.posts.update_one({"_id": post["_id"]}, {"$set": {
        "reactions": post["reactions"]
    }})

    # Send event
    app.cl.send_event("post_reaction_add", {
        "chat_id": post["post_origin"],
        "post_id": post["_id"],
        "emoji": emoji_reaction,
        "username": request.user
    })

    return {"error": False}, 200

@posts_bp.delete("/<post_id>/reactions/<emoji_reaction>/<username>")
async def remove_post_reaction(post_id: str, emoji_reaction: str, username: str):
    # Check authorization
    if not request.user:
        abort(401)

    # @me -> requester
    if username == "@me":
        username = request.user

    # Ratelimit
    if security.ratelimited(f"react:{request.user}"):
        abort(429)
    security.ratelimit(f"react:{request.user}", 5, 5)

    # Make sure reaction exists
    if not db.post_reactions.count_documents({"_id": {
        "post_id": post_id,
        "emoji": emoji_reaction,
        "user": username
    }}, limit=1):
        abort(404)

    # Get necessary post details and check access
    post = db.posts.find_one({
        "_id": post_id,
        "isDeleted": {"$ne": True}
    }, projection={
        "_id": 1,
        "post_origin": 1,
        "u": 1,
        "reactions": 1
    })
    if not post:
        abort(404)
    elif post["post_origin"] == "inbox" and post["u"] not in ["Server", request.user]:
        abort(404)
    elif post["post_origin"] not in ["home", "inbox"]:
        chat = db.chats.find_one({
            "_id": post["post_origin"],
            "members": request.user,
            "deleted": False
        }, projection={"owner": 1})
        if not chat:
            abort(404)

    # Make sure requester can remove the reaction
    if request.user != username:
        if (post["post_origin"] in ["home", "inbox"]) or (chat["owner"] != request.user):
            abort(403)

    # Remove reaction
    db.post_reactions.delete_one({"_id": {
        "post_id": post["_id"],
        "emoji": emoji_reaction,
        "user": username
    }})

    # Update post
    for reaction in post["reactions"]:
        if reaction["emoji"] != emoji_reaction:
            continue
        reaction["count"] = db.post_reactions.count_documents({
            "_id.post_id": post["_id"],
            "_id.emoji": reaction["emoji"]
        })
        if not reaction["count"]:
            post["reactions"].remove(reaction)
        break
    db.posts.update_one({"_id": post["_id"]}, {"$set": {
        "reactions": post["reactions"]
    }})

    # Send event
    app.cl.send_event("post_reaction_remove", {
        "chat_id": post["post_origin"],
        "post_id": post["_id"],
        "emoji": emoji_reaction,
        "username": username
    })

    return {"error": False}, 200

from quart import Blueprint, current_app as app, request, abort
from quart_schema import validate_querystring, validate_request
from pydantic import BaseModel, Field
from typing import Literal, Optional
import pymongo
import uuid
import time

import security, models, errors
from entities import users
from database import db, get_total_pages
from cloudlink import cl3_broadcast


users_bp = Blueprint("users_bp", __name__, url_prefix="/users/<username>")

class GetPostsQueryArgs(BaseModel):
    page: Optional[int] = Field(default=1, ge=1)

class UpdateRelationshipBody(BaseModel):
    state: Literal[
        0,  # no relationship
        #1,  # following (doesn't do anything yet)
        2,  # blocking
    ]

    class Config:
        validate_assignment = True


@users_bp.before_request
async def get_user():
    username: str = request.view_args["username"]
    try:
        if username.startswith("$"):
            try:
                user_id = int(username[1:])
            except ValueError:
                abort(400)
            request.requested_user = users.get_user(user_id)
        else:
            request.requested_user = users.get_user_by_username(username)
    except errors.UserNotFound:
        abort(404)
    else:
        if not request.requested_user:
            abort(500)


@users_bp.get("/")
async def get_user(_):
    user = users.db_to_v0(
        request.requested_user,
        (request.user["_id"] == request.requested_user["_id"]),
    )
    user["error"] = False
    return user


@users_bp.get("/posts")
@validate_querystring(GetPostsQueryArgs)
async def get_posts(username, query_args: GetPostsQueryArgs):
    # Get posts
    query = {"post_origin": "home", "isDeleted": False, "u": username}
    posts = list(db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(query_args.page-1)*25, limit=25))

    # Return posts
    return {
        "error": False,
        "autoget": posts,
        "page#": query_args.page,
        "pages": get_total_pages("posts", query)
    }, 200


@users_bp.get("/relationship")
async def get_relationship(username):
    # Check authorization
    if not request.user:
        abort(401)

    # Make sure the requested user isn't the requester
    if request.user == username:
        abort(400)

    # Get relationship
    relationship = db.relationships.find_one({"_id": {"from": request.user, "to": username}})

    # Return relationship
    if relationship:
        del relationship["_id"]
        return relationship, 200
    else:
        return {
            "state": 0,
            "updated_at": None
        }, 200


@users_bp.patch("/relationship")
@validate_request(UpdateRelationshipBody)
async def update_relationship(username, data: UpdateRelationshipBody):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if await security.ratelimited(f"relationships:{request.user}"):
        abort(429)

    # Ratelimit
    await security.ratelimit(f"relationships:{request.user}", 10, 15)

    # Make sure the requested user isn't the requester
    if request.user == username:
        abort(400)

    # Get relationship
    relationship = db.relationships.find_one({"_id": {"from": request.user, "to": username}})
    if not relationship:
        relationship = {
            "_id": {"from": request.user, "to": username},
            "state": 0,
            "updated_at": None
        }

    # Make sure the state relationship state changed
    if data.state == relationship["state"]:
        del relationship["_id"]
        return relationship, 200

    # Update relationship
    relationship["state"] = data.state
    relationship["updated_at"] = int(time.time())
    if data.state == 0:
        db.relationships.delete_one({"_id": {"from": request.user, "to": username}})
    else:
        db.relationships.update_one({"_id": {"from": request.user, "to": username}}, {"$set": relationship}, upsert=True)

    # Sync relationship between sessions
    await cl3_broadcast({
        "mode": "update_relationship",
        "payload": {
            "username": username,
            "state": relationship["state"],
            "updated_at": relationship["updated_at"]
        }
    }, direct_wrap=True, usernames=[request.user])

    # Return updated relationship
    del relationship["_id"]
    return relationship, 200


@users_bp.get("/dm")
async def get_dm_chat(username):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if await security.ratelimited(f"create_chat:{request.user}"):
        abort(429)

    # Ratelimit
    await security.ratelimit(f"create_chat:{request.user}", 5, 30)

    # Make sure the requested user isn't the requester
    if request.user == username:
        abort(400)

    # Get existing chat or create new chat
    chat = db.chats.find_one({
        "members": {"$all": [request.user, username]},
        "type": 1,
        "deleted": False
    })
    if not chat:
        # Check restrictions
        if security.is_restricted(request.user, security.Restrictions.NEW_CHATS):
            return {"error": True, "type": "accountBanned"}, 403

        # Create chat
        chat = {
            "_id": str(uuid.uuid4()),
            "type": 1,
            "nickname": None,
            "owner": None,
            "members": [request.user, username],
            "created": int(time.time()),
            "last_active": 0,
            "deleted": False
        }
        db.chats.insert_one(chat)

    # Return chat
    if chat["last_active"] == 0:
        chat["last_active"] = int(time.time())
    return chat, 200

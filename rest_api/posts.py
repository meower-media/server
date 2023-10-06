from flask import Blueprint, current_app as app, request, abort
from pydantic import BaseModel, Field
from threading import Thread
import pymongo
import uuid
import time


posts_bp = Blueprint("posts_bp", __name__, url_prefix="/posts")


class PostBody(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


@posts_bp.get("")
def get_post():
    # Get post ID
    post_id = request.args.get("id")
    if not post_id:
        abort(400)
    
    # Get post
    post = app.files.db.posts.find_one({"_id": post_id})
    if not post:
        abort(404)

    # Check access
    if post["isDeleted"]:
        abort(404)
    elif (post["post_origin"] == "inbox") and (post["u"] != request.user):
        abort(404)
    elif post["post_origin"] != "home":
        if app.files.db.chats.count_documents({
            "_id": post["post_origin"],
            "members": request.user,
            "deleted": False
        }, limit=1) < 1:
            abort(404)

    # Return post
    post["error"] = False
    return post, 200


@posts_bp.patch("")
def update_post():
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"post:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"post:{request.user}", 6, 5)

    # Get body
    try:
        body = PostBody(**request.json)
    except: abort(400)

    # Get post ID
    post_id = request.args.get("id")
    if not post_id:
        abort(400)
    
    # Get post
    post = app.files.db.posts.find_one({"_id": post_id})
    if not post:
        abort(404)

    # Check access
    if post["isDeleted"]:
        abort(404)
    elif post["post_origin"] not in {"home", "inbox"}:
        chat = app.files.db.chats.find_one({
            "_id": post["post_origin"],
            "members": request.user,
            "deleted": False
        }, projection={"members": 1})
        if not chat:
            abort(404)
    if post["post_origin"] == "inbox" or post["u"] != request.user:
        abort(403)

    # Check ban state
    if app.security.get_ban_state(request.user) in {"TempSuspension", "PermSuspension"}:
        return {"error": True, "type": "accountBanned"}, 403

    # Make sure new content isn't the same as the old content
    if post.get("unfiltered_p") or post["p"] == body.content:
        post["error"] = False
        return post, 200

    # Add revision
    app.files.db.post_revisions.insert_one({
        "_id": str(uuid.uuid4()),
        "post_id": post["_id"],
        "old_content": post.get("unfiltered_p") or post["p"],
        "new_content": body.content,
        "time": int(time.time())
    })

    # Update post
    post["edited_at"] = int(time.time())
    filtered_content = app.supporter.wordfilter(body.content)
    if filtered_content != body.content:
        post["p"] = filtered_content
        post["unfiltered_p"] = body.content
        app.files.db.posts.update_one({"_id": post_id}, {"$set": {
            "p": post["p"],
            "unfiltered_p": post["unfiltered_p"],
            "edited_at": post["edited_at"]
        }})
    else:
        post["p"] = body.content
        if "unfiltered_p" in post:
            del post["unfiltered_p"]
        app.files.db.posts.update_one({"_id": post_id}, {"$set": {
            "p": post["p"],
            "edited_at": post["edited_at"]
        }, "$unset": {
            "unfiltered_p": ""
        }})

    # Send update post event
    if post["post_origin"] == "home":
        app.supporter.sendPacket({"cmd": "direct", "val": {
            "mode": "update_post",
            "payload": post
        }})
    else:
        app.supporter.sendPacket({"cmd": "direct", "val": {
            "mode": "update_post",
            "payload": post
        }, "id": chat["members"]})

    # Return post
    post["error"] = False
    return post, 200


@posts_bp.delete("")
def delete_post():
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"post:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"post:{request.user}", 6, 5)

    # Get post ID
    post_id = request.args.get("id")
    if not post_id:
        abort(400)
    
    # Get post
    post = app.files.db.posts.find_one({"_id": post_id})
    if not post:
        abort(404)

    # Check access
    if post["isDeleted"]:
        abort(404)
    elif post["post_origin"] not in {"home", "inbox"}:
        chat = app.files.db.chats.find_one({
            "_id": post["post_origin"],
            "members": request.user,
            "deleted": False
        }, projection={"owner": 1, "members": 1})
        if not chat:
            abort(404)
    if post["post_origin"] == "inbox" or post["u"] != request.user:
        if post["post_origin"] in {"home", "inbox"}:
            abort(403)
        elif chat["owner"] != request.user:
            abort(403)

    # Update post
    app.files.db.posts.update_one({"_id": post_id}, {"$set": {
        "isDeleted": True,
        "deleted_at": int(time.time())
    }})

    # Send delete post event
    if post["post_origin"] == "home":
        app.supporter.sendPacket({"cmd": "direct", "val": {
            "mode": "delete",
            "id": post_id
        }})
    else:
        app.supporter.sendPacket({"cmd": "direct", "val": {
            "mode": "delete",
            "id": post_id
        }, "id": chat["members"]})

    return {"error": False}, 200


@posts_bp.get("/<chat_id>")
def get_chat_posts(chat_id):
    # Check authorization
    if not request.user:
        abort(401)

    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Make sure chat exists
    if app.files.db.chats.count_documents({
        "_id": chat_id,
        "members": request.user,
        "deleted": False
    }, limit=1) < 1:
        abort(404)

    # Get posts
    query = {"post_origin": chat_id, "isDeleted": False}
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("posts", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@posts_bp.post("/<chat_id>")
def create_chat_post(chat_id):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"post:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"post:{request.user}", 6, 5)

    # Get body
    try:
        body = PostBody(**request.json)
    except: abort(400)

    # Check ban state
    if app.security.get_ban_state(request.user) in {"TempSuspension", "PermSuspension"}:
        return {"error": True, "type": "accountBanned"}, 403

    if chat_id != "livechat":
        # Get chat
        chat = app.files.db.chats.find_one({
            "_id": chat_id,
            "members": request.user,
            "deleted": False
        }, projection={"type": 1, "members": 1})
        if not chat:
            abort(404)
        
        # DM stuff
        if chat["type"] == 1:
            # Check privacy options
            if app.files.db.relationships.count_documents({"$or": [
                {"_id": {"from": chat["members"][0], "to": chat["members"][1]}},
                {"_id": {"from": chat["members"][1], "to": chat["members"][0]}}
            ], "state": 2}, limit=1) > 0:
                abort(403)

            # Update user settings
            Thread(target=app.files.db.user_settings.bulk_write, args=([
                pymongo.UpdateMany({"$or": [
                    {"_id": chat["members"][0]},
                    {"_id": chat["members"][1]}
                ]}, {"$pull": {"active_dms": chat_id}}),
                pymongo.UpdateMany({"$or": [
                    {"_id": chat["members"][0]},
                    {"_id": chat["members"][1]}
                ]}, {"$push": {"active_dms": {
                    "$each": [chat_id],
                    "$position": 0,
                    "$slice": -150
                }}})
            ],)).start()

    # Create post
    FileWrite, post = app.supporter.createPost(chat_id, request.user, body.content, chat_members=(chat["members"] if chat_id != "livechat" else None))
    if not FileWrite:
        abort(500)

    # Return new post
    return post, 200

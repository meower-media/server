from quart import Blueprint, current_app as app, request, abort
from pydantic import BaseModel, Field
import uuid
import time

from security import Restrictions


chats_bp = Blueprint("chats_bp", __name__, url_prefix="/chats")


class ChatBody(BaseModel):
    nickname: str = Field(min_length=1, max_length=32)

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


@chats_bp.get("")
async def get_chats():
    # Check authorization
    if not request.user:
        abort(401)

    # Get active DMs and favorited chats
    user_settings = app.files.db.user_settings.find_one({"_id": request.user}, projection={
        "active_dms": 1,
        "favorited_chats": 1
    })
    if not user_settings:
        user_settings = {
            "active_dms": [],
            "favorited_chats": []
        }
    if "active_dms" not in user_settings:
        user_settings["active_dms"] = []
    if "favorited_chats" not in user_settings:
        user_settings["favorited_chats"] = []

    # Get chats
    chats = list(app.files.db.chats.find({
        "deleted": False,
        "members": request.user,
        "$or": [
            {"type": 0},
            {
                "type": 1,
                "_id": {"$in": user_settings["active_dms"] + user_settings["favorited_chats"]}
            }
        ]
    }, hint="user_chats"))

    # Return chats
    payload = {
        "error": False,
        "page#": 1,
        "pages": 1
    }
    if "autoget" in request.args:
        payload["autoget"] = chats
    else:
        payload["index"] = [chat["_id"] for chat in chats]
    return payload, 200


@chats_bp.post("")
async def create_chat():
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"create_chat:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"create_chat:{request.user}", 5, 30)

    # Check restrictions
    if app.security.is_restricted(request.user, Restrictions.NEW_CHATS):
        return {"error": True, "type": "accountBanned"}, 403

    # Get body
    try:
        body = ChatBody(**await request.json)
    except: abort(400)
    
    # Make sure the requester isn't in too many chats
    if app.files.db.chats.count_documents({"type": 0, "members": request.user}, limit=150) >= 150:
        return {"error": True, "type": "tooManyChats"}, 403

    # Create chat
    chat = {
        "_id": str(uuid.uuid4()),
        "type": 0,
        "nickname": app.supporter.wordfilter(body.nickname),
        "owner": request.user,
        "members": [request.user],
        "created": int(time.time()),
        "last_active": int(time.time()),
        "deleted": False
    }
    app.files.db.chats.insert_one(chat)

    # Tell the requester the chat was created
    app.supporter.sendPacket({"cmd": "direct", "val": {
        "mode": "create_chat",
        "payload": chat
    }, "id": request.user})

    # Return chat
    chat["error"] = False
    return chat, 200


@chats_bp.get("/<chat_id>")
async def get_chat(chat_id):
    # Check authorization
    if not request.user:
        abort(401)

    # Get chat
    chat = app.files.db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
    if not chat:
        abort(404)

    # Return chat
    chat["error"] = False
    return chat, 200


@chats_bp.patch("/<chat_id>")
async def update_chat(chat_id):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Get body
    try:
        body = ChatBody(**await request.json)
    except: abort(400)

    # Check restrictions
    if body.nickname and app.security.is_restricted(request.user, Restrictions.EDITING_CHAT_NICKNAMES):
        return {"error": True, "type": "accountBanned"}, 403

    # Get chat
    chat = app.files.db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
    if not chat:
        abort(404)

    # Make sure requester is owner
    if chat["owner"] != request.user:
        abort(403)

    # Make sure new nickname isn't the same as the old nickname
    if chat["nickname"] == body.nickname:
        chat["error"] = False
        return chat, 200
    
    # Update chat
    chat["nickname"] = app.supporter.wordfilter(body.nickname)
    app.files.db.chats.update_one({"_id": chat_id}, {"$set": {"nickname": chat["nickname"]}})

    # Send update chat event
    app.supporter.sendPacket({"cmd": "direct", "val": {
        "mode": "update_chat",
        "payload": {
            "_id": chat_id,
            "nickname": chat["nickname"]
        }
    }, "id": chat["members"]})

    # Send in-chat notification
    app.supporter.createPost(chat_id, "Server", f"@{request.user} changed the nickname of the group chat to '{chat['nickname']}'.", chat_members=chat["members"])

    # Return chat
    chat["error"] = False
    return chat, 200


@chats_bp.delete("/<chat_id>")
async def leave_chat(chat_id):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Get chat
    chat = app.files.db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
    if not chat:
        abort(404)

    if chat["type"] == 0:
        # Remove member
        chat["members"].remove(request.user)

        # Update chat if it's not empty, otherwise delete the chat
        if len(chat["members"]) > 0:
            # Transfer ownership, if owner
            if chat["owner"] == request.user:
                chat["owner"] = chat["members"][0]
            
            # Update chat
            app.files.db.chats.update_one({"_id": chat_id}, {
                "$set": {"owner": chat["owner"]},
                "$pull": {"members": request.user}
            })

            # Send update chat event
            app.supporter.sendPacket({"cmd": "direct", "val": {
                "mode": "update_chat",
                "payload": {
                    "_id": chat_id,
                    "owner": chat["owner"],
                    "members": chat["members"]
                }
            }, "id": chat["members"]})

            # Send in-chat notification
            app.supporter.createPost(chat_id, "Server", f"@{request.user} has left the group chat.", chat_members=chat["members"])
        else:
            app.files.db.posts.delete_many({"post_origin": chat_id, "isDeleted": False})
            app.files.db.chats.delete_one({"_id": chat_id})
    elif chat["type"] == 1:
        # Remove chat from requester's active DMs list
        app.files.db.user_settings.update_one({"_id": request.user}, {
            "$pull": {"active_dms": chat_id}
        })
    else:
        abort(500)

    # Send delete event to client
    app.supporter.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": chat_id}, "id": request.user})

    return {"error": False}, 200


@chats_bp.put("/<chat_id>/members/<username>")
async def add_chat_member(chat_id, username):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Check restrictions
    if app.security.is_restricted(request.user, Restrictions.NEW_CHATS):
        return {"error": True, "type": "accountBanned"}, 403

    # Get chat
    chat = app.files.db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
    if not chat:
        abort(404)

    # Make sure the chat isn't full
    if chat["type"] == 1 or len(chat["members"]) >= 256:
        return {"error": True, "type": "chatFull"}, 403

    # Make sure the user isn't already in the chat
    if username in chat["members"]:
        return {"error": True, "type": "chatMemberAlreadyExists"}, 409

    # Make sure requested user exists and isn't deleted
    user = app.files.db.usersv0.find_one({"_id": username}, projection={"permissions": 1})
    if (not user) or (user["permissions"] is None):
        abort(404)

    # Make sure requested user isn't blocked or is blocking client
    if app.files.db.relationships.count_documents({"$or": [
        {
            "_id": {"from": request.user, "to": username},
            "state": 2
        },
        {
            "_id": {"from": username, "to": request.user},
            "state": 2
        }
    ]}, limit=1) > 0:
        abort(403)

    # Update chat
    chat["members"].append(username)
    app.files.db.chats.update_one({"_id": chat_id}, {"$addToSet": {"members": username}})

    # Send create chat event
    app.supporter.sendPacket({"cmd": "direct", "val": {
        "mode": "create_chat",
        "payload": chat
    }, "id": username})

    # Send update chat event
    app.supporter.sendPacket({"cmd": "direct", "val": {
        "mode": "update_chat",
        "payload": {
            "_id": chat_id,
            "members": chat["members"]
        }
    }, "id": chat["members"]})

    # Send inbox message to user
    app.supporter.createPost("inbox", username, f"You have been added to the group chat '{chat['nickname']}' by @{request.user}!")

    # Send in-chat notification
    app.supporter.createPost(chat_id, "Server", f"@{request.user} added @{username} to the group chat.", chat_members=chat["members"])

    # Return chat
    chat["error"] = False
    return chat, 200


@chats_bp.delete("/<chat_id>/members/<username>")
async def remove_chat_member(chat_id, username):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Get chat
    chat = app.files.db.chats.find_one({
        "_id": chat_id,
        "members": {"$all": [request.user, username]},
        "deleted": False
    })
    if not chat:
        abort(404)

    # Make sure requester is owner
    if chat["owner"] != request.user:
        abort(403)

    # Update chat
    chat["members"].remove(username)
    app.files.db.chats.update_one({"_id": chat_id}, {"$pull": {"members": username}})

    # Send update chat event
    app.supporter.sendPacket({"cmd": "direct", "val": {
        "mode": "update_chat",
        "payload": {
            "_id": chat_id,
            "members": chat["members"]
        }
    }, "id": chat["members"]})

    # Send delete chat event to user
    app.supporter.sendPacket({"cmd": "direct", "val": {"mode": "delete", "id": chat_id}, "id": username})

    # Send inbox message to user
    app.supporter.createPost("inbox", username, f"You have been removed from the group chat '{chat['nickname']}' by @{request.user}!")

    # Send in-chat notification
    app.supporter.createPost(chat_id, "Server", f"@{request.user} removed @{username} from the group chat.", chat_members=chat["members"])

    # Return chat
    chat["error"] = False
    return chat, 200


@chats_bp.post("/<chat_id>/members/<username>/transfer")
async def transfer_chat_ownership(chat_id, username):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Get chat
    chat = app.files.db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
    if not chat:
        abort(404)

    # Make sure requester is owner
    if chat["owner"] != request.user:
        abort(403)

    # Make sure requested user isn't already owner
    if chat["owner"] == username:
        chat["error"] = False
        return chat, 200

    # Make sure the user is in the chat
    if username not in chat["members"]:
        abort(404)

    # Update chat
    chat["owner"] = username
    app.files.db.chats.update_one({"_id": chat_id}, {"$set": {"owner": username}})

    # Send update chat event
    app.supporter.sendPacket({"cmd": "direct", "val": {
        "mode": "update_chat",
        "payload": {
            "_id": chat_id,
            "owner": chat["owner"]
        }
    }, "id": chat["members"]})

    # Send in-chat notification
    app.supporter.createPost(chat_id, "Server", f"@{request.user} transferred ownership of the group chat to @{username}.", chat_members=chat["members"])

    # Return chat
    chat["error"] = False
    return chat, 200

from quart import Blueprint, current_app as app, request, abort
from quart_schema import validate_request
from pydantic import BaseModel, Field
from typing import Optional
import uuid, time

import security
from database import db
from meowid import gen_id
from uploads import claim_file, delete_file
from utils import log

chats_bp = Blueprint("chats_bp", __name__, url_prefix="/chats")


class GetPostsQueryArgs(BaseModel):
    page: Optional[int] = Field(default=1, ge=1)

class ChatBody(BaseModel):
    nickname: str = Field(default=None, min_length=1, max_length=32)
    icon: str = Field(default=None, max_length=24)
    icon_color: str = Field(default=None, min_length=6, max_length=6)  # hex code without the #
    allow_pinning: bool = Field(default=None)

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


@chats_bp.post("/")
@validate_request(ChatBody)
async def create_chat(data: ChatBody):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"create_chat:{request.user}"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"create_chat:{request.user}", 5, 30)

    # Check restrictions
    if security.is_restricted(request.user, security.Restrictions.NEW_CHATS):
        return {"error": True, "type": "accountBanned"}, 403
    
    # Make sure the requester isn't in too many chats
    if db.chats.count_documents({"type": 0, "members": request.user}, limit=150) >= 150:
        return {"error": True, "type": "tooManyChats"}, 403

    # Claim icon
    if data.icon:
        try:
            claim_file(data.icon, "icons")
        except Exception as e:
            log(f"Unable to claim icon: {e}")
            return {"error": True, "type": "unableToClaimIcon"}, 500

    # Create chat
    if data.icon is None:
        data.icon = ""
    if data.icon_color is None:
        data.icon_color = "000000"
    if data.allow_pinning is None:
        data.allow_pinning = False
    chat = {
        "_id": str(uuid.uuid4()),
        "meowid": await gen_id(),
        "type": 0,
        "nickname": data.nickname,
        "icon": data.icon,
        "icon_color": data.icon_color,
        "owner": request.user,
        "members": [request.user],
        "created": int(time.time()),
        "last_active": int(time.time()),
        "deleted": False,
        "allow_pinning": data.allow_pinning
    }
    db.chats.insert_one(chat)

    # Add emotes
    chat.update({
        "emojis": list(db.chat_emojis.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0})),
        "stickers": list(db.chat_stickers.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0}))
    })


    # Tell the requester the chat was created
    app.cl.send_event("create_chat", chat, usernames=[request.user])

    # Return chat
    chat["error"] = False
    return chat, 200


@chats_bp.patch("/<chat_id>")
@validate_request(ChatBody)
async def update_chat(chat_id, data: ChatBody):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Check restrictions
    if security.is_restricted(request.user, security.Restrictions.EDITING_CHAT_DETAILS):
        return {"error": True, "type": "accountBanned"}, 403

    # Get chat
    chat = db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
    if not chat:
        abort(404)

    # Make sure requester is owner
    if chat["owner"] != request.user:
        abort(403)

    # Get updated values
    updated_vals = {"_id": chat_id}
    if data.nickname is not None and chat["nickname"] != data.nickname:
        updated_vals["nickname"] = data.nickname
        await app.supporter.create_post(chat_id, "Server", f"@{request.user} changed the nickname of the group chat to '{chat['nickname']}'.", chat_members=chat["members"])
    if data.icon is not None and chat["icon"] != data.icon:
        # Claim icon (and delete old one)
        if data.icon != "":
            try:
                updated_vals["icon"] = claim_file(data.icon, "icons")["id"]
            except Exception as e:
                log(f"Unable to claim icon: {e}")
                return {"error": True, "type": "unableToClaimIcon"}, 500
        if chat["icon"]:
            try:
                delete_file(chat["icon"])
            except Exception as e:
                log(f"Unable to delete icon: {e}")
        await app.supporter.create_post(chat_id, "Server", f"@{request.user} changed the icon of the group chat.", chat_members=chat["members"])
    if data.icon_color is not None and chat["icon_color"] != data.icon_color:
        updated_vals["icon_color"] = data.icon_color
        if data.icon is None or chat["icon"] == data.icon:
            await app.supporter.create_post(chat_id, "Server", f"@{request.user} changed the icon of the group chat.", chat_members=chat["members"])
    if data.allow_pinning is not None:
        updated_vals["allow_pinning"] = data.allow_pinning
    
    # Update chat
    db.chats.update_one({"_id": chat_id}, {"$set": updated_vals})

    # Send update chat event
    app.cl.send_event("update_chat", updated_vals, usernames=chat["members"])

    # Return chat
    chat.update({
        "error": False,
        "emojis": list(db.chat_emojis.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0})),
        "stickers": list(db.chat_stickers.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0}))
    })
    return chat, 200


@chats_bp.put("/<chat_id>/members/<username>")
async def add_chat_member(chat_id, username):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Check restrictions
    if security.is_restricted(request.user, security.Restrictions.NEW_CHATS):
        return {"error": True, "type": "accountBanned"}, 403

    # Get chat
    chat = db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
    if not chat:
        abort(404)

    # Make sure the chat isn't full
    if chat["type"] == 1 or len(chat["members"]) >= 256:
        return {"error": True, "type": "chatFull"}, 403

    # Make sure the user isn't already in the chat
    if username in chat["members"]:
        return {"error": True, "type": "chatMemberAlreadyExists"}, 409

    # Make sure requested user exists and isn't deleted
    user = db.usersv0.find_one({"_id": username}, projection={"permissions": 1})
    if (not user) or (user["permissions"] is None):
        abort(404)

    # Make sure requested user isn't blocked or is blocking client
    if db.relationships.count_documents({"$or": [
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
    db.chats.update_one({"_id": chat_id}, {"$addToSet": {"members": username}})

    # Send create chat event
    app.cl.send_event("create_chat", chat, usernames=[username])

    # Send update chat event
    app.cl.send_event("update_chat", {
        "_id": chat_id,
        "members": chat["members"]
    }, usernames=chat["members"])

    # Send inbox message to user
    await app.supporter.create_post("inbox", username, f"You have been added to the group chat '{chat['nickname']}' by @{request.user}!")

    # Send in-chat notification
    await app.supporter.create_post(chat_id, "Server", f"@{request.user} added @{username} to the group chat.", chat_members=chat["members"])

    # Return chat
    chat.update({
        "error": False,
        "emojis": list(db.chat_emojis.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0})),
        "stickers": list(db.chat_stickers.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0}))
    })
    return chat, 200


@chats_bp.delete("/<chat_id>/members/<username>")
async def remove_chat_member(chat_id, username):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Get chat
    chat = db.chats.find_one({
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
    db.chats.update_one({"_id": chat_id}, {"$pull": {"members": username}})

    # Send delete chat event to user
    app.cl.send_event("delete_chat", {"chat_id": chat_id}, usernames=[username])

    # Send update chat event
    app.cl.send_event("update_chat", {
        "_id": chat_id,
        "members": chat["members"]
    }, usernames=chat["members"])

    # Send inbox message to user
    await app.supporter.create_post("inbox", username, f"You have been removed from the group chat '{chat['nickname']}' by @{request.user}!")

    # Send in-chat notification
    await app.supporter.create_post(chat_id, "Server", f"@{request.user} removed @{username} from the group chat.", chat_members=chat["members"])

    # Return chat
    chat.update({
        "error": False,
        "emojis": list(db.chat_emojis.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0})),
        "stickers": list(db.chat_stickers.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0}))
    })
    return chat, 200


@chats_bp.post("/<chat_id>/members/<username>/transfer")
async def transfer_chat_ownership(chat_id, username):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Get chat
    chat = db.chats.find_one({
        "_id": chat_id,
        "members": {"$all": [request.user, username]},
        "deleted": False
    })
    if not chat:
        abort(404)

    # Make sure requester is owner
    if chat["owner"] != request.user:
        abort(403)

    # Make sure requested user isn't already owner
    if chat["owner"] == username:
        chat["error"] = False
        return chat, 200

    # Update chat
    chat["owner"] = username
    db.chats.update_one({"_id": chat_id}, {"$set": {"owner": username}})

    # Send update chat event
    app.cl.send_event("update_chat", {
        "_id": chat_id,
        "owner": chat["owner"]
    }, usernames=chat["members"])

    # Send in-chat notification
    await app.supporter.create_post(chat_id, "Server", f"@{request.user} transferred ownership of the group chat to @{username}.", chat_members=chat["members"])

    # Return chat
    chat.update({
        "error": False,
        "emojis": list(db.chat_emojis.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0})),
        "stickers": list(db.chat_stickers.find({
            "chat_id": chat["_id"]
        }, projection={"chat_id": 0, "created_at": 0, "created_by": 0}))
    })
    return chat, 200

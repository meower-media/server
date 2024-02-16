import secrets

from quart import Blueprint, Response, current_app as app, request, abort
from pydantic import BaseModel, Field
import uuid
import time

import security
from database import db
from .api_types import AuthenticatedRequest, MeowerQuart

request: AuthenticatedRequest
app: MeowerQuart

chats_bp = Blueprint("chats_bp", __name__, url_prefix="/chats")


class ChatBody(BaseModel):
    nickname: str = Field(min_length=1, max_length=32)

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


@chats_bp.get("/")
async def get_chats():
    # Check authorization
    if not request.user:
        abort(401)

    # Get active DMs and favorited chats
    user_settings = db.user_settings.find_one({"_id": request.user}, projection={
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
    chats = list(db.chats.find({"$or": [
        {  # DMs
            "_id": {
                "$in": user_settings["active_dms"] + user_settings["favorited_chats"]
            },
            "members": request.user,
            "deleted": False
        },
        {  # group chats
            "members": request.user,
            "type": 0,
            "deleted": False
        }
    ]}))

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


@chats_bp.post("/")
async def create_chat():
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

    # Get body
    try:
        body = ChatBody(**await request.json)
    except: abort(400)
    
    # Make sure the requester isn't in too many chats
    if db.chats.count_documents({"type": 0, "members": request.user}, limit=150) >= 150:
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
    db.chats.insert_one(chat)

    # Tell the requester the chat was created
    app.cl.broadcast({
        "mode": "create_chat",
        "payload": chat
    }, direct_wrap=True, usernames=[request.user])

    # Return chat
    chat["error"] = False
    return chat, 200


@chats_bp.get("/<chat_id>")
async def get_chat(chat_id):
    # Check authorization
    if not request.user:
        abort(401)

    # Get chat
    chat = db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
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
    if security.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Get body
    try:
        body = ChatBody(**await request.json)
    except: abort(400)

    # Check restrictions
    if body.nickname and security.is_restricted(request.user, security.Restrictions.EDITING_CHAT_NICKNAMES):
        return {"error": True, "type": "accountBanned"}, 403

    # Get chat
    chat = db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
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
    db.chats.update_one({"_id": chat_id}, {"$set": {"nickname": chat["nickname"]}})

    # Send update chat event
    app.cl.broadcast({
        "mode": "update_chat",
        "payload": {
            "_id": chat_id,
            "nickname": chat["nickname"]
        }
    }, direct_wrap=True, usernames=chat["members"])

    # Send in-chat notification
    app.supporter.create_post(chat_id, "Server", f"@{request.user} changed the nickname of the group chat to '{chat['nickname']}'.", chat_members=chat["members"])

    # Return chat
    chat["error"] = False
    return chat, 200


@chats_bp.delete("/<chat_id>")
async def leave_chat(chat_id):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"update_chat:{request.user}", 5, 5)

    # Get chat
    chat = db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
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
            db.chats.update_one({"_id": chat_id}, {
                "$set": {"owner": chat["owner"]},
                "$pull": {"members": request.user}
            })

            # Send update chat event
            app.cl.broadcast({
                "mode": "update_chat",
                "payload": {
                    "_id": chat_id,
                    "owner": chat["owner"],
                    "members": chat["members"]
                }
            }, direct_wrap=True, usernames=chat["members"])

            # Send in-chat notification
            app.supporter.create_post(chat_id, "Server", f"@{request.user} has left the group chat.", chat_members=chat["members"])
        else:
            db.posts.delete_many({"post_origin": chat_id, "isDeleted": False})
            db.chats.delete_one({"_id": chat_id})
    elif chat["type"] == 1:
        # Remove chat from requester's active DMs list
        db.user_settings.update_one({"_id": request.user}, {
            "$pull": {"active_dms": chat_id}
        })
    else:
        abort(500)

    # Send delete event to client
    app.cl.broadcast({
        "mode": "delete",
        "id": chat_id
    }, direct_wrap=True, usernames=[request.user])

    return {"error": False}, 200


@chats_bp.post("/<chat_id>/typing")
async def emit_typing(chat_id):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"typing:{request.user}"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"typing:{request.user}", 6, 5)

    # Check restrictions
    if security.is_restricted(request.user, security.Restrictions.CHAT_POSTS):
        return {"error": True, "type": "accountBanned"}, 403

    # Get chat
    if chat_id != "livechat":
        chat = db.chats.find_one({
            "_id": chat_id,
            "members": request.user,
            "deleted": False
        }, projection={"members": 1})
        if not chat:
            abort(404)

    # Send new state
    # noinspection PyUnboundLocalVariable
    app.cl.broadcast({
        "chatid": chat_id,
        "u": request.user,
        "state": 100
    }, direct_wrap=True, usernames=(None if chat_id == "livechat" else chat["members"]))

    return {"error": False}, 200


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

    if db["chat_bans"].find_one({"_id": (username, chat["_id"])}) is not None:
        return {"error": True, "type": "chatBanned"}, 401

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
    app.cl.broadcast({
        "mode": "create_chat",
        "payload": chat
    }, direct_wrap=True, usernames=[username])

    # Send update chat event
    app.cl.broadcast({
        "mode": "update_chat",
        "payload": {
            "_id": chat_id,
            "members": chat["members"]
        }
    }, direct_wrap=True, usernames=chat["members"])

    # Send inbox message to user
    app.supporter.create_post("inbox", username, f"You have been added to the group chat '{chat['nickname']}' by @{request.user}!")

    # Send in-chat notification
    app.supporter.create_post(chat_id, "Server", f"@{request.user} added @{username} to the group chat.", chat_members=chat["members"])

    # Return chat
    chat["error"] = False
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
    app.cl.broadcast({
        "mode": "delete",
        "id": chat_id
    }, direct_wrap=True, usernames=[username])

    # Send update chat event
    app.cl.broadcast({
        "mode": "update_chat",
        "id": {
            "_id": chat_id,
            "members": chat["members"]
        }
    }, direct_wrap=True, usernames=chat["members"])

    # Send inbox message to user
    app.supporter.create_post("inbox", username, f"You have been removed from the group chat '{chat['nickname']}' by @{request.user}!")

    # Send in-chat notification
    app.supporter.create_post(chat_id, "Server", f"@{request.user} removed @{username} from the group chat.", chat_members=chat["members"])

    # Return chat
    chat["error"] = False
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
    app.cl.broadcast({
        "mode": "update_chat",
        "payload": {
            "_id": chat_id,
            "owner": chat["owner"]
        }
    }, direct_wrap=True, usernames=chat["members"])

    # Send in-chat notification
    app.supporter.create_post(chat_id, "Server", f"@{request.user} transferred ownership of the group chat to @{username}.", chat_members=chat["members"])

    # Return chat
    chat["error"] = False
    return chat, 200

@chats_bp.post("/<chat_id>/invites")
async def create_invite(chat_id):
    if not request.user:
        abort(401)

    # get chat
    chat = db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
    if not chat:
        abort(404)

    if chat["owner"] is None:
        abort(403)


    if security.ratelimited("update_chat:{request.user}"):
        abort(429)

    security.ratelimit("update_chat:{request.user}", 5, 5)

    invite = secrets.token_urlsafe(4) \
        .replace("-", 'a')           \
        .replace('_', 'b')           \
        .replace("=", 'c')

    db.chat_invites.insert_one({
        "chat_id": chat_id,
        "_id": invite
    })

    return {"error": False, "invite": invite}, 200

@chats_bp.get("/<chat_id>/invites")
async def get_invites(chat_id):
    if not request.user:
        abort(401)


    # get chat
    chat = db.chats.find_one({"_id": chat_id, "members": request.user, "deleted": False})
    if not chat:
        abort(404)

    invites = db.chat_invites.find({"chat_id": chat_id})
    if not invites:
        abort(404)



    invites = list(invites)

    return {"error": False, "invites": invites}, 200

@chats_bp.delete("/invites/<invite>")
async def delete_invite(invite):
    if not request.user:
        abort(401)

    if len(invite) > 8:
        abort(400)

    if security.ratelimited("update_chat:{request.user}"):
        abort(429)

    security.ratelimit("update_chat:{request.user}", 5, 5)

    invite = db.chat_invites.find_one({"_id": invite})
    if not invite:
        abort(404)

    chat = db.chats.find_one({"_id": invite["chat_id"]})
    if not chat:
        abort(404)

    if chat["owner"] != request.user:
        abort(403)

    db.chat_invites.delete_one({"_id": invite})

    return {"error": False}, 200

@chats_bp.get("/join/<invite>")
async def join_invite(invite):
    if not request.user:
        abort(401)

    if len(invite) > 8:
        abort(400)

    invite = db.chat_invites.find_one({"_id": invite})
    if not invite:
        abort(404)

    chat = db.chats.find_one({"_id": invite["chat_id"]})
    if not chat:
        abort(404)

    if request.user in chat["members"]:
        return {"error": True, "type": "chatMemberAlreadyExists"}, 409

    if db["chat_bans"].find_one({"_id": (request.user, chat["_id"])}) is not None:
        abort(403)

    if  len(chat["members"]) >= 256:
        return {"error": True, "type": "chatFull"}, 403

    db.chats.update_one({"_id": chat["_id"]}, {"$addToSet": {"members": request.user}})
    app.supporter.create_post(chat["_id"], "Server", f" @{request.user} has joined the group chat via invite {invite['_id']}", chat_members=chat["members"])

    app.cl.broadcast({
        "mode": "create_chat",
        "payload": chat
    }, direct_wrap=True,  usernames=[request.user])

    app.cl.broadcast({
        "mode": "update_chat",
        "payload": {
            "_id": invite["chat_id"],
            "members": chat["members"]
        }
    }, direct_wrap=True, users = chat["members"] + [request.user])

    return {"error": False, "chat": chat["_id"]}, 200

@chats_bp.put("/<chat_id>/bans/<username>")
async def ban_user(chat_id, username):

    if not request.user:
        abort(401)

    if security.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    security.ratelimit(f"update_chat:{request.user}", 5, 5)

    chat = db.chats.find_one({"_id": chat_id})

    if not chat:
        abort(404)

    if chat["owner"] != request.user:
        abort(403)

    if request.user == username:
        abort(403)

    if username not in chat["members"]:
        abort(404)

    # Update chat
    message = (await request.body).decode('utf-8')
    chat["members"].remove(username)
    db.chats.update_one({"_id": chat_id}, {"$pull": {"members": username}})
    db.chat_bans.insert_one({
        "_id": (username, chat_id)
    })
    # Send update chat event
    app.cl.broadcast({
        "mode": "update_chat",
        "payload": {
            "_id": chat_id,
            "members": chat["members"]
        }
    },  direct_wrap=True, usernames=chat["members"])

    # Send delete chat event to user
    app.cl.broadcast({"mode": "delete", "id": chat_id},  direct_wrap=True, usernames=[username])

    # Send inbox message to user
    app.supporter.create_post("inbox", username, f"You have been removed from the group chat '{chat['nickname']}' by @{request.user}!\n Reason: {message}")

    # Send in-chat notification
    app.supporter.create_post(chat_id, "Server", f"@{request.user} removed @{username} from the group chat, with the reason: \n{message}", chat_members=chat["members"])

    return {"error": False}, 200

@chats_bp.delete("/<chat_id>/bans/<username>")
async def unban_user(chat_id, username):

    if not request.user:
        abort(401)

    if security.ratelimited(f"update_chat:{request.user}"):
        abort(429)

    security.ratelimit(f"update_chat:{request.user}", 5, 5)

    chat = db.chats.find_one({"_id": chat_id})
    if not chat:
        abort(404)

    if chat["owner"] != request.user:
        abort(403)

    db.chat_bans.delete_one({"chat": chat_id, "username": username})

    return {"error": False}, 200

@chats_bp.get("/<chat_id>/bans")
async def get_bans(chat_id):
    if not request.user:
        abort(401)

    chat = db.chats.find_one({"_id": chat_id})
    if not chat:
        abort(404)

    if chat["owner"] != request.user:
        abort(403)

    bans = db.chat_bans.find({"chat": chat_id})
    if not bans:
        return {"error": False, "bans": []}, 200

    ret = []
    for ban in bans:
        ret.append({
            "username": ban["username"],
            "message": ban["message"]
        })

    return {"error": False, "bans": list(ret)}, 200
from src.cl3.server import cl
from src.util import uid, events
from src.entities import users, infractions


@events.on("user_updated")
async def user_updated(user_id: str, payload: dict):
    if user_id in cl._user_ids:
        if (payload.get("id") == "0") or ("username" in payload):
            await cl.kick_client(cl._user_ids[user_id])


@events.on("session_deleted")
async def session_deleted(user_id: str, payload: dict):
    return
    await send_to_user(user_id, "session_deleted", payload)
    for client in cl._users.get(user_id, set()):
        if client.session_id == payload["id"]:
            await client.close(code=3000, reason="Session revoked")


@events.on("notification_count_updated")
async def notification_count_updated(user_id: str, payload: dict):
    if payload["unread"] > 0:
        if user_id in cl._user_ids:
            await cl.send_to_client(cl._user_ids[user_id], {
                "cmd": "direct",
                "val": {
                    "mode": "inbox_message",
                    "payload": {}
                }
            })


@events.on("infraction_created")
async def infraction_created(user_id: str, payload: dict):
    if user_id in cl._user_ids:
        user = users.get_user(user_id)
        moderation_status = infractions.user_status(user)
        if moderation_status["banned"]:
            await cl.kick_client(cl._user_ids[user_id], "Banned")


@events.on("infraction_updated")
async def infraction_updated(user_id: str, payload: dict):
    if user_id in cl._user_ids:
        user = users.get_user(user_id)
        moderation_status = infractions.user_status(user)
        if moderation_status["banned"]:
            await cl.kick_client(cl._user_ids[user_id], "Banned")


@events.on("infraction_deleted")
async def infraction_deleted(user_id: str, payload: dict):
    if user_id in cl._user_ids:
        user = users.get_user(user_id)
        moderation_status = infractions.user_status(user)
        if moderation_status["banned"]:
            await cl.kick_client(cl._user_ids[user_id], "Banned")


@events.on("post_created")
async def post_created(post_id: str, payload: dict):
    await cl.broadcast({
        "cmd": "direct",
        "val": {
            "type": 1,
            "post_origin": "home",
            "u": payload["author"]["username"],
            "t": uid.timestamp(epoch=payload["time"], jsonify=True),
            "p": (payload["filtered_content"] if payload["filtered_content"] else payload["content"]),
            "post_id": post_id,
            "isDeleted": False,
            "_id": post_id,
            "mode": 1
        }
    })


@events.on("post_deleted")
async def post_deleted(post_id: str, payload: dict):
    await cl.broadcast({
        "cmd": "direct",
        "val": {
            "mode": "delete",
            "id": post_id
        }
    })

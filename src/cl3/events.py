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
    if user_id in cl._user_ids:
        if cl._user_ids[user_id].session_id == payload["id"]:
            await cl.kick_client(cl._user_ids[user_id])


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


@events.on("chat_created")
async def chat_created(user_id: str, payload: dict):
    if payload["id"] not in cl._chats:
        cl._chats[payload["id"]] = set()
    if user_id in cl._user_ids:
        cl._chats[payload["id"]].add(cl._user_ids[user_id])


@events.on("chat_deleted")
async def chat_deleted(user_id: str, payload: dict):
    if payload["id"] in cl._chats:
        if user_id in cl._user_ids:
            cl._chats[payload["id"]].remove(cl._user_ids[user_id])
        if len(cl._chats[payload["id"]]) == 0:
            del cl._chats[payload["id"]]


@events.on("message_created")
async def message_created(chat_id: str, payload: dict):
    await cl.send_to_chat(chat_id, {
        "cmd": "direct",
        "val": {
            "type": 1,
            "post_origin": chat_id,
            "u": payload["author"]["username"],
            "t": uid.timestamp(epoch=payload["time"], jsonify=True),
            "p": (payload["filtered_content"] if payload["filtered_content"] else payload["content"]),
            "post_id": payload["id"],
            "isDeleted": False,
            "_id": payload["id"],
            "state": 2
        }
    })


@events.on("message_deleted")
async def message_deleted(chat_id: str, payload: dict):
    await cl.send_to_chat(chat_id, {
        "cmd": "direct",
        "val": {
            "mode": "delete",
            "id": payload["id"]
        }
    })


@events.on("cl_direct")
async def cl_direct(user_id: str, payload: dict):
    if user_id in cl._user_ids:
        await cl.send_to_client(cl._user_ids[user_id], {
            "cmd": "pmsg",
            "origin": users.get_user(payload["origin"]).username,
            "val": payload["val"]
        })

from src.cl4.server import cl
from src.util import events


async def send_to_user(user_id: str, cmd: str, val: dict):
    cl.send_packet(
        clients=cl._users.get(user_id, set()),
        message={
            "cmd": cmd,
            "val": val
        }
    )


async def on_connect(client):
    client.user_id = None
    client.session_id = None


@events.on("user_updated")
async def user_updated(user_id: str, payload: dict):
    if payload.get("id") == "0":
        if user_id in cl._subscriptions["users"]:
            del cl._subscriptions["users"][user_id]
            return

    await send_to_user(user_id, "user_updated", payload)

    for key in payload.keys():
        if key in {"flags", "admin", "bot_session", "redirect_to", "delete_after"}:
            del payload[key]
    
    cl.send_packet_multicast(
        clients=cl._users.get(user_id, set()),
        message={
            "cmd": "user_updated",
            "val": payload
        }
    )


@events.on("user_config_updated")
async def user_config_updated(user_id: str, payload: dict):
    await send_to_user(user_id, "user_config_updated", payload)


@events.on("relationship_updated")
async def relationship_updated(user_id: str, payload: dict):
    await send_to_user(user_id, "relationship_updated", payload)


@events.on("session_created")
async def session_created(user_id: str, payload: dict):
    await send_to_user(user_id, "session_created", payload)


@events.on("session_updated")
async def session_updated(user_id: str, payload: dict):
    await send_to_user(user_id, "session_updated", payload)


@events.on("session_deleted")
async def session_deleted(user_id: str, payload: dict):
    await send_to_user(user_id, "session_deleted", payload)
    cl.close_connection(
        obj=cl._users.get(user_id, set()),
        code=3000,
        reason="Session revoked"
    )


@events.on("notification_count_updated")
async def notification_count_updated(user_id: str, payload: dict):
    await send_to_user(user_id, "notification_count_updated", payload)


@events.on("infraction_created")
async def infraction_created(user_id: str, payload: dict):
    await send_to_user(user_id, "infraction_created", payload)


@events.on("infraction_updated")
async def infraction_updated(user_id: str, payload: dict):
    await send_to_user(user_id, "infraction_updated", payload)


@events.on("infraction_deleted")
async def infraction_deleted(user_id: str, payload: dict):
    await send_to_user(user_id, "infraction_deleted", payload)


@events.on("post_created")
async def post_created(post_id: str, payload: dict):
    cl.send_packet_multicast(
        clients=cl._subscriptions["new_posts"],
        message={
            "cmd": "post_created",
            "val": payload
        }
    )


@events.on("post_updated")
async def post_updated(post_id: str, payload: dict):
    cl.send_packet_multicast(
        clients=cl._subscriptions["posts"].get(post_id, set()),
        message={
            "cmd": "post_updated",
            "val": payload
        }
    )


@events.on("post_deleted")
async def post_deleted(post_id: str, payload: dict):
    cl.send_packet_multicast(
        clients=cl._subscriptions["posts"].get(post_id, set()),
        message={
            "cmd": "post_deleted",
            "val": payload
        }
    )
    
    if post_id in cl._subscriptions["posts"]:
        del cl._subscriptions["posts"][post_id]


@events.on("post_status_updated")
async def post_status_updated(user_id: str, payload: dict):
    await send_to_user(user_id, "post_status_updated", payload)


@events.on("chat_created")
async def chat_created(user_id: str, payload: dict):
    if payload["id"] not in cl._subscriptions["chats"]:
        cl._subscriptions["chats"][payload["id"]] = set()
    for client in cl._users.get(user_id, set()):
        cl._subscriptions["chats"][payload["id"]].add(client)
    await send_to_user(user_id, "chat_created", payload)


@events.on("chat_updated")
async def chat_updated(chat_id: str, payload: dict):
    cl.send_packet_multicast(
        clients=cl._subscriptions["chats"].get(chat_id, set()),
        message={
            "cmd": "chat_updated",
            "val": payload
        }
    )


@events.on("chat_deleted")
async def chat_deleted(user_id: str, payload: dict):
    for client in cl._users.get(user_id, set()):
        if client in cl._subscriptions["chats"].get(payload["id"], set()):
            cl._subscriptions["chats"][payload["id"]].remove(client)
    if (payload["id"] in cl._subscriptions["chats"]) and (len(cl._subscriptions["chats"][payload["id"]]) == 0):
        del cl._subscriptions["chats"][payload["id"]]
    await send_to_user(user_id, "chat_deleted", payload)


@events.on("typing_start")
async def typing_start(chat_id: str, payload: dict):
    cl.send_packet_multicast(
        clients=cl._subscriptions["chats"].get(chat_id, set()),
        message={
            "cmd": "typing_start",
            "val": payload
        }
    )


@events.on("message_created")
async def message_created(chat_id: str, payload: dict):
    cl.send_packet_multicast(
        clients=cl._subscriptions["chats"].get(chat_id, set()),
        message={
            "cmd": "message_created",
            "val": payload
        }
    )


@events.on("message_updated")
async def message_updated(chat_id: str, payload: dict):
    cl.send_packet_multicast(
        clients=cl._subscriptions["chats"].get(chat_id, set()),
        message={
            "cmd": "message_updated",
            "val": payload
        }
    )


@events.on("message_deleted")
async def message_deleted(chat_id: str, payload: dict):
    cl.send_packet_multicast(
        clients=cl._subscriptions["chats"].get(chat_id, set()),
        message={
            "cmd": "message_deleted",
            "val": payload
        }
    )


@events.on("cl_direct")
async def cl_direct(user_id: str, payload: dict):
    await send_to_user(user_id, "direct", payload)

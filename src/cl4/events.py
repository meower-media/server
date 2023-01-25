from src.cl4.server import cl
from src.util import events

async def send_to_user(user_id: str, cmd: str, val: dict):
    await cl.send_packet_multicast(
        cmd,
        val,
        clients=cl._users.get(user_id, set())
    )

async def on_connect(client):
    client.user_id = None
    client.session_id = None

@events.on("sync_updated")
async def sync_updated(payload: dict):
    user_id = payload.pop("user_id")
    await send_to_user(user_id, "sync_updated", payload)

@events.on("session_created")
async def session_created(payload: dict):
    user_id = payload.pop("user_id")
    await send_to_user(user_id, "session_created", payload)

@events.on("session_updated")
async def session_updated(payload: dict):
    user_id = payload.pop("user_id")
    await send_to_user(user_id, "session_updated", payload)

@events.on("session_deleted")
async def session_deleted(payload: dict):
    user_id = payload.pop("user_id")
    await send_to_user(user_id, "session_deleted", payload)
    for client in cl._users.get(user_id, set()):
        if client.session_id == payload["id"]:
            await client.close(code=3000, reason="Session revoked")

@events.on("notification_created")
async def notification_created(payload: dict):
    recipient_id = payload.pop("recipient_id")
    await send_to_user(recipient_id, "notification_created", payload)

@events.on("notification_updated")
async def notification_updated(payload: dict):
    recipient_id = payload.pop("recipient_id")
    await send_to_user(recipient_id, "notification_updated", payload)

@events.on("notification_deleted")
async def notification_deleted(payload: dict):
    recipient_id = payload.pop("recipient_id")
    await send_to_user(recipient_id, "notification_deleted", payload)

@events.on("infraction_created")
async def infraction_created(payload: dict):
    user_id = payload.pop("user_id")
    await send_to_user(user_id, "infraction_created", payload)

@events.on("infraction_updated")
async def infraction_updated(payload: dict):
    user_id = payload.pop("user_id")
    await send_to_user(user_id, "infraction_updated", payload)

@events.on("infraction_deleted")
async def infraction_deleted(payload: dict):
    user_id = payload.pop("user_id")
    await send_to_user(user_id, "infraction_deleted", payload)

@events.on("post_created")
async def post_created(payload: dict):
    await cl.send_packet_multicast(
        "post_created",
        payload,
        clients=cl._subscriptions["new_posts"]
    )

@events.on("post_updated")
async def post_updated(payload: dict):
    await cl.send_packet_multicast(
        "post_updated",
        payload,
        clients=cl._subscriptions["posts"].get(payload["id"], set())
    )

@events.on("post_deleted")
async def post_deleted(payload: dict):
    await cl.send_packet_multicast(
        "post_deleted",
        payload,
        clients=cl._subscriptions["posts"].get(payload["id"], set())
    )
    if payload["id"] in cl._subscriptions["posts"]:
        del cl._subscriptions["posts"][payload["id"]]

@events.on("post_status_updated")
async def post_status_updated(payload: dict):
    user_id = payload.pop("user_id")
    await send_to_user(user_id, "post_status_updated", payload)

@events.on("chat_created")
async def chat_created(payload: dict):
    chat = payload.pop("chat")
    user_id = payload.pop("user_id")
    if chat["id"] not in cl._subscriptions["chats"]:
        cl._subscriptions["chats"][chat["id"]] = set()
    for client in cl._users.get(user_id, set()):
        cl._subscriptions["chats"][chat["id"]].add(client)
    await send_to_user(user_id, "chat_created", chat)

@events.on("chat_updated")
async def chat_updated(payload: dict):
    await cl.send_packet_multicast(
        "chat_updated",
        payload,
        clients=cl._subscriptions["chats"].get(payload["id"], set())
    )

@events.on("chat_deleted")
async def chat_deleted(payload: dict):
    chat_id = payload.pop("id")
    user_id = payload.pop("user_id")
    for client in cl._users.get(user_id, set()):
        if client in cl._subscriptions["chats"].get(chat_id, set()):
            cl._subscriptions["chats"][chat_id].remove(client)
    if (chat_id in cl._subscriptions["chats"]) and (len(cl._subscriptions["chats"][chat_id]) == 0):
        del cl._subscriptions["chats"][chat_id]
    await send_to_user(user_id, "chat_deleted", {"id": chat_id})

@events.on("typing_start")
async def typing_start(payload: dict):
    await cl.send_packet_multicast(
        "typing_start",
        payload,
        clients=cl._subscriptions["chats"].get(payload["chat_id"], set())
    )

@events.on("message_created")
async def message_created(payload: dict):
    await cl.send_packet_multicast(
        "message_created",
        payload,
        clients=cl._subscriptions["chats"].get(payload["chat_id"], set())
    )

@events.on("message_updated")
async def message_updated(payload: dict):
    await cl.send_packet_multicast(
        "message_updated",
        payload,
        clients=cl._subscriptions["chats"].get(payload["chat_id"], set())
    )

@events.on("message_deleted")
async def message_deleted(payload: dict):
    await cl.send_packet_multicast(
        "message_deleted",
        payload,
        clients=cl._subscriptions["chats"].get(payload["chat_id"], set())
    )

@events.on("cl_direct")
async def cl_direct(payload: dict):
    user_id = payload.pop("id")
    await send_to_user(user_id, "direct", payload)

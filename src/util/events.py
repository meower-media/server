from threading import Thread
import json
import asyncio

from src.database import redis

EVENT_NAMES = set([
    "user_updated",
    "sync_updated",
    "session_created",
    "session_updated",
    "session_deleted",
    "notification_count_updated",
    "infraction_created",
    "infraction_updated",
    "infraction_deleted",
    "post_created",
    "post_updated",
    "post_deleted",
    "post_status_updated",
    "comment_created",
    "comment_updated",
    "comment_deleted",
    "comment_status_updated",
    "chat_created",
    "chat_updated",
    "chat_deleted",
    "typing_start",
    "message_created",
    "message_updated",
    "message_deleted",
    "cl_direct"
])

def emit_event(name: str, identifier: str, message: any):
    if name not in EVENT_NAMES:
        raise
    redis.publish(f"meower:{name}", json.dumps({"i": identifier, "m": message}))

def add_event_listener(name: str, callback: callable):
    def run():
        pubsub = redis.pubsub()
        pubsub.subscribe(f"meower:{name}")
        for message in pubsub.listen():
            try:
                data = json.loads(message.get("data"))
                identifier = data["i"]
                message = data["m"]
                asyncio.run(callback(identifier, message))
            except:
                continue
    
    thread = Thread(target=run)
    thread.daemon = True
    thread.start()

def on(event_name: str):
    def decorator(func: callable) -> callable:
        add_event_listener(event_name, func)
        return func
    return decorator

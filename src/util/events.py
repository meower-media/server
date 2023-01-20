from threading import Thread
import json

from src.database import redis

EVENT_NAMES = set([
    "user_updated",
    "sync_updated",
    "session_created",
    "session_updated",
    "session_deleted",
    "infraction_created",
    "infraction_updated",
    "infraction_deleted",
    "post_created",
    "post_updated",
    "post_deleted",
    "post_liked",
    "post_meowed",
    "post_unliked",
    "post_unmeowed",
    "chat_created",
    "chat_updated",
    "chat_deleted",
    "message_created",
    "message_updated",
    "message_deleted"
])

def emit_event(name: str, details: dict = {}):
    if name not in EVENT_NAMES:
        raise
    redis.publish(f"meower:{name}", json.dumps(details))

def add_event_listener(name: str, callback: callable):
    def run():
        pubsub = redis.pubsub()
        pubsub.subscribe(f"meower:{name}")
        for message in pubsub.listen():
            if not isinstance(message, dict):
                continue

            message = message.get("data")
            try:
                message = json.loads(message.decode())
            except:
                continue
        
            callback(message)
    
    thread = Thread(run)
    thread.daemon = True
    thread.start()

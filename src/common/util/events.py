from threading import Thread
import ujson
import asyncio

from src.common.database import redis


def send_event(event: str, payload: dict):
    redis.publish("meower", ujson.dumps({"event": event, "payload": payload}))


def add_event_listener(callback: callable):
    def run():
        pubsub = redis.pubsub()
        pubsub.subscribe("meower")
        for message in pubsub.listen():
            try:
                message = ujson.loads(message["data"])
                asyncio.run(callback(message["event"], message["payload"]))
            except:
                continue
    
    runner_thread = Thread(target=run)
    runner_thread.daemon = True
    runner_thread.start()

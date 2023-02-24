from src.cl3.server import cl
from src.util import uid, events


@events.on("post_created")
async def post_created(post_id: str, payload: dict):
    await cl.broadcast({
        "cmd": "direct",
        "val": {
            "type": 1,
            "post_origin": "home",
            "u": payload["author"]["username"],
            "t": uid.timestamp(epoch=payload["time"], jsonify=True),
            "p": payload["content"],
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

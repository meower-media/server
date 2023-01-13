from datetime import datetime, timezone
import time
import os

from .snowflake import generate_snowflake

MEOWER_EPOCH = 0  # NEVER CHANGE THIS

def timestamp(epoch: int = None, jsonify: bool = False) -> dict|datetime:
    if epoch is None:
        dt = datetime.now(tz=timezone.utc)
    else:
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)

    if jsonify:
        return {
            "h": dt.hour,
            "mi": dt.minute,
            "s": dt.second,
            "d": dt.day,
            "mo": dt.month,
            "y": dt.year,
            "e": int(dt.timestamp())
        }
    else:
        return dt

def snowflake() -> str:
    return str(generate_snowflake(
        worker_id=int(os.getenv("WORKER_ID", 0)),
        datacenter_id=int(os.getenv("DATACENTER_ID", 0)),
        epoch=MEOWER_EPOCH
    ))

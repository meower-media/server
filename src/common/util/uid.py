from datetime import datetime, timezone
from uuid import uuid4


def timestamp(epoch: int = None, jsonify: bool = False) -> dict|datetime:
    if epoch:
        dt = datetime.fromtimestamp(epoch, tz=(timezone.utc if jsonify else None))
    else:
        dt = datetime.now(tz=(timezone.utc if jsonify else None))

    if jsonify:
        return {
            "mo": dt.strftime("%m"),
            "d": dt.strftime("%d"),
            "y": dt.strftime("%Y"),
            "h": dt.strftime("%H"),
            "mi": dt.strftime("%M"),
            "s": dt.strftime("%S"),
            "e": int(dt.timestamp())
        }
    else:
        return dt

def uuid() -> str:
    return str(uuid4())

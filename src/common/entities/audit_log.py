import time

from src.common.util import uid
from src.common.database import db, count_pages


class Log:
    def __init__(
        self,
        _id: str,
        action: str,
        moderator: str,
        data: dict,
        time: int
    ):
        self.id = _id
        self.action = action
        self.moderator = moderator
        self.data = data
        self.time = time

    @property
    def admin(self):
        return {
            "_id": self.id,
            "action": self.action,
            "moderator": self.moderator,
            "data": self.data,
            "time": self.time
        }
    
    def delete(self):
        db.audit_log.delete_one({"_id": self.id})


def create_log(action: str, moderator: str, data: dict):
    # Create log data
    log_data = {
        "_id": uid.uuid(),
        "action": action,
        "moderator": moderator,
        "data": data,
        "time": int(time.time())
    }

    # Insert log into database
    db.audit_log.insert_one(log_data)

    # Return log object
    return Log(**log_data)


def get_logs(page: int = 1) -> list[Log]:
    return count_pages("audit_log", {}), [Log(**log) for log in db.audit_log.find({},
                                                   sort=[("time", -1)],
                                                   skip=((page-1)*25),
                                                   limit=25)]

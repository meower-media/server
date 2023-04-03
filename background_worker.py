import time

from src.common.entities import users
from src.common.util import config, display_startup, logging
from src.common.database import db


def scheduled_account_deletions():
    for user in db.users.find({"delete_after": {"$gte": int(time.time())}}):
        users.User(**user).delete()


if __name__ == "__main__":
    display_startup()

    try:
        while True:
            time.sleep(60)
            for task in [scheduled_account_deletions]:
                if config.development:
                    logging.info(f"Running task {task.__name__}...")
                task()
    except KeyboardInterrupt:
        exit()

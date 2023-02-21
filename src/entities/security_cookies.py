from base64 import b64encode, b64decode
import json
import time

from src.util import uid, security
from src.entities import users

class SecurityCookie:
    def __init__(
        self,
        _id: str,
        version: int = 1,
        users: list = [],
        last_used: dict = {}
    ):
        self.id = _id
        self.version = version
        self.users = [users.get_user(user["id"]) for user in users]
        self.last_used = last_used

    @property
    def signed_cookie(self):
        encoded_data = b64encode(json.dumps({
            "_id": self.id,
            "version": self.version,
            "users": [user.id for user in self.users],
            "last_used": self.last_used
        }).encode()).decode()
        signature = security.sign("security_cookies", encoded_data)
        return f"{encoded_data}.{signature}"

    def add_user(self, user: any):
        self.users.append(user)
        self.users = list(set(self.users))
        self.last_used[user.id] = int(time.time())

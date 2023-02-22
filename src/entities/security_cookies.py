from base64 import b64encode, b64decode
import json
import time
import zlib

from src.util import uid, bitfield, flags, security
from src.entities import users

class SecurityCookie:
    def __init__(
        self,
        i: str,
        v: int,
        u: list,
        t: dict
    ):
        self.id = i
        self.version = v
        self.users = [users.get_user(user_id) for user_id in u]
        self.last_used = t

        for user in self.users:
            if (self.last_used[user.id]+7776000 < time.time()) or bitfield.has(user.flags, flags.users.system) or bitfield.has(user.flags, flags.users.deleted):
                self.users.remove(user)
                if user.id in self.last_used:
                    del self.last_used[user.id]

    @property
    def signed_cookie(self):
        encoded_data = b64encode(zlib.compress(json.dumps({
            "i": self.id,
            "v": self.version,
            "u": list(set([user.id for user in self.users])),
            "t": self.last_used
        }).encode()))
        signature = security.sign_data(encoded_data)
        return f"{encoded_data.decode()}.{signature.decode()}"

    def add_user(self, user):
        if user.id not in [_user.id for _user in self.users]:
            self.users.append(user)
        self.last_used[user.id] = int(time.time())

def decode_security_cookie(cookie: str = None):
    try:
        encoded_data, signature = cookie.split(".")
        encoded_data = encoded_data.encode()
        signature = signature.encode()
        if not security.validate_signature(signature, encoded_data): raise Exception
        security_cookie = json.loads(zlib.decompress(b64decode(encoded_data)).decode())
        return SecurityCookie(**security_cookie)
    except Exception as e:
        print(e)
        return SecurityCookie(uid.snowflake(), 1, [], {})

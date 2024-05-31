import models


class UsernameExists(Exception): pass

class UserNotFound(Exception): pass

class InvalidCredentials(Exception): pass

class UserBanned(Exception):
    def __init__(self, ban: models.db.UserBan):
        self.ban = ban

class SessionNotFound(Exception): pass

class MFANotVerified(Exception): pass

class Ratelimited(Exception): pass

class ChatNotFound(Exception): pass

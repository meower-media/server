from src.util import status, bitfield, flags
from src.entities import users
from src.database import db

class Bot:
    def __init__(
        self,
        _id: str,
        owner_id: str = None
    ):
        self._id = _id
        self.owner = users.get_user(owner_id)

def create_bot(username: str, owner: users.User):
    if not users.username_available(username):
        raise status.alreadyExists
    
    user = users.create_user(username, flags=bitfield.create([flags.user.bot]))

    bot = {
        "_id": user.id,
        "owner_id": owner.id
    }
    db.bots.insert_one(bot)

    return Bot(**bot)

def get_bot(user_id: str):
    bot = db.bots.find_one({"_id": user_id})

    if bot is None:
        raise status.notFound
    else:
        return Bot(**bot)

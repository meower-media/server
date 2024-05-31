import pymongo
from typing import Optional

import models, errors
from . import ids, users
from database import db


def db_to_v0(chat: models.db.Chat) -> models.v0.Chat:
    owner_username = None
    if "owner_id" in chat:
        owner_username = users.get_min_user(chat["owner_id"])["username"]
    member_usernames = [
        users.get_min_user(member["_id"]["user_id"])["username"]
        for member in db.chat_members.find({"_id.chat_id": chat["_id"]}, projection={
            "_id": 1
        })
    ]
    return {
        "_id": str(chat["_id"]),
        "type": chat["type"],
        "nickname": chat.get("nickname"),
        "icon": chat.get("icon", ""),
        "icon_color": chat.get("icon_color", "000000"),
        "owner_id": str(chat["owner_id"]) if "owner_id" else None,
        "owner": owner_username,
        "members": member_usernames,
        "allow_pinning": chat.get("allow_pinning", True),
        "created": ids.extract_timestamp(chat["_id"]),
        "last_post_id": chat.get("last_post_id", chat["_id"]),
        "last_active": ids.extract_timestamp(chat.get("last_post_id", chat["_id"]))
    }

def create_group_chat(nickname: str, owner_id: int) -> models.db.Chat:
    chat: models.db.Chat = {
        "_id": ids.gen_id(),
        "type": 0,
        "nickname": nickname,
        "owner_id": owner_id
    }
    db.chats.insert_one(chat)
    return chat

def get_chat(chat_id: int) -> models.db.Chat:
    chat: models.db.Chat = db.chats.find_one({"_id": chat_id})
    if chat:
        return chat
    else:
        raise errors.ChatNotFound

def get_all_chats(user_id: int) -> tuple[dict[str, models.db.ChatMember], list[models.db.Chat]]:
    """
    Returns a dict of chat memberships, and a list of chats.
    """

    memberships = {member["_id"]["chat_id"]: member for member in db.chat_members.find({
        "_id.user_id": user_id,
        "closed": {"$ne": True}
    })}
    chats = [get_chat(chat_id) for chat_id in memberships.keys()]
    return memberships, chats

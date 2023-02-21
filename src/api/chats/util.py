from src.util import status
from src.entities import users, chats


def get_chat_or_abort_if_no_membership(chat_id: str, user: any):
    chat = chats.get_chat(chat_id)
    if chat and chat.has_member(user):
        return chat
    else:
        raise status.resourceNotFound

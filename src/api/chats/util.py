from src.util import status
from src.entities import users, chats

def get_chat_or_abort_if_no_membership(chat_id: str, user: users.User):
    chat = chats.get_chat(chat_id)
    if (chat is None) or (not chat.has_member(user)):
        raise status.notFound
    return chat

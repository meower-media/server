from sanic import Blueprint

# v1
from .general import v1 as v1_general
from .members import v1 as v1_members
from .messages import v1 as v1_messages
v1 = Blueprint.group(
    v1_general,
    v1_members,
    v1_messages,
    url_prefix="/chats/<chat_id:str>"
)


from src.util import status
from src.entities import users, chats
def get_chat_or_abort_if_no_membership(chat_id: str, user: users.User):
    chat = chats.get_chat(chat_id)
    if (chat is None) or (not chat.has_member(user)):
        raise status.notFound
    return chat

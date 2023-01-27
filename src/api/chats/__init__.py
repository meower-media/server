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

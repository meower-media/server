from sanic import Blueprint, text, json
import time

from src.util import uid
from src.database import db, redis

unversioned = Blueprint("unversioned_general", url_prefix="/")
v0 = Blueprint("v0_general", url_prefix="/")
v1 = Blueprint("v1_general", url_prefix="/")


@unversioned.get("/status")
async def unversioned_status(request):
    return json({
        "isRepairMode": (redis.exists("repair_mode") == 1),
        "scratchDeprecated": (time.time() > 1688169599),
        "supported": {
            0: (not time.time() > 1688169599),
            1: True
        },
        "supportedGateway": {
            "cl3": (not time.time() > 1688169599),
            "cl4": True
        }
    })


@v0.get("/")
async def v0_welcome(request):
    return text(f"Welcome to v0 of the Meower API! Meower API v0 will no longer function on {uid.timestamp(epoch=1688169600).isoformat()}. Please use Meower API v1.")


@v1.get("/")
async def v1_welcome(request):
    return text("Welcome to v1 of the Meower API! This is the most current API version.")


@v0.get("/ip")
async def v0_get_client_ip(request):
    return text(request.ip)


@v0.get("/statistics")
async def v0_statistics(request):
    users = db.users.estimated_document_count()
    posts = db.posts.estimated_document_count()
    chats = db.chats.estimated_document_count()

    return json({"error": False, "users": users, "posts": posts, "chats": chats})


@v1.get("/statistics")
async def v1_statistics(request):
    return json({
        "accounts": db.accounts.estimated_document_count(),
        "bots": db.bots.estimated_document_count(),
        "posts": db.posts.estimated_document_count(),
        "post_likes": db.post_likes.estimated_document_count(),
        "post_meows": db.post_meows.estimated_document_count(),
        "chats": db.chats.estimated_document_count(),
        "chat_messages": db.chat_messages.estimated_document_count(),
        "infractions": db.infractions.estimated_document_count()
    })

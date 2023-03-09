from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from redis import Redis
import os

from src.util import logging


# Connect to MongoDB
try:
    db = MongoClient(os.getenv("DB_URI", "mongodb://127.0.0.1:27017"))[os.getenv("DB_NAME", "meowercl4")]
except Exception as e:
    logging.error(f"Failed connecting to database: {str(e)}")


# Connect to Redis
try:
    redis = Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        password=os.getenv("REDIS_PASSWORD")
    )
except Exception as e:
    logging.error(f"Failed connecting to Redis: {str(e)}")


# Initialize database
DB_COLLECTIONS = []

def rebuild_indexes():  # needs to be improved
    # Delete all indexes
    for collection in db.list_collection_names():
        db[collection].drop_indexes()

    # Users
    db.users.create_index([("lower_username", ASCENDING)], name="username", unique=True)
    db.users.create_index([("lower_username", TEXT), ("_id", DESCENDING)], name="search")

    # Accounts
    db.accounts.create_index([("email", ASCENDING)], name="email", unique=True, sparse=True)

    # Applications
    db.applications.create_index([("maintainers", ASCENDING)], name="maintainers")

    # Netlog
    db.netlog.create_index([("_id.user_id", ASCENDING)], name="user")
    db.netlog.create_index([("_id.ip_address", ASCENDING)], name="ip")

    # Notifications
    db.notifications.create_index([("recipient_id", ASCENDING), ("unread", ASCENDING), ("time", DESCENDING), ("_id", ASCENDING)], name="recipient_notifications")

    # User sessions
    db.sessions.create_index([("user_id", ASCENDING)], name="user")
    db.sessions.create_index([("legacy_token", ASCENDING)], name="legacy_sessions", unique=True, sparse=True)

    # OAuth sessions
    db.oauth_sessions.create_index([("application_id", ASCENDING), ("user_id", ASCENDING)], name="application_and_user")

    # Authorized apps
    db.authorized_apps.create_index([("_id.application_id", ASCENDING), ("_id.user_id", ASCENDING)], name="application_and_user")

    # Infractions
    db.infractions.create_index([("user_id", ASCENDING)], name="user")
    db.infractions.create_index([("time", DESCENDING), ("_id", ASCENDING)], name="latest")

    # Followed users
    db.followed_users.create_index([("_id.to", ASCENDING), ("time", DESCENDING), ("_id.from", ASCENDING)], name="to")
    db.followed_users.create_index([("_id.from", ASCENDING), ("time", DESCENDING), ("_id.to", ASCENDING)], name="from")

    # Blocked users
    db.blocked_users.create_index([("_id.from", ASCENDING)], name="from")

    # Profile history
    db.profile_history.create_index([("user_id", ASCENDING)], name="user")

    # Posts
    db.posts.create_index([("deleted_at", ASCENDING), ("time", DESCENDING), ("author_id", ASCENDING), ("_id", ASCENDING)], name="feed")
    db.posts.create_index([("deleted_at", ASCENDING), ("reputation", DESCENDING), ("_id", ASCENDING)], name="trending")
    db.posts.create_index([("deleted_at", ASCENDING), ("content", TEXT), ("time", DESCENDING), ("_id", ASCENDING)], name="search_content")
    db.posts.create_index([("deleted_at", ASCENDING), ("author_id", ASCENDING), ("time", DESCENDING), ("_id", ASCENDING)], name="search_author")

    # Post revisions
    db.post_revisions.create_index([("post_id", ASCENDING)], name="post")

    # Post likes
    db.post_likes.create_index([("_id.post_id", ASCENDING)], name="post")

    # Post meows
    db.post_meows.create_index([("_id.post_id", ASCENDING)], name="post")
    db.post_meows.create_index([("time", DESCENDING), ("_id.user_id", ASCENDING)], name="feed")

    # Comments
    db.post_comments.create_index([("post_id", ASCENDING), ("parent_id", ASCENDING), ("deleted_at", ASCENDING), ("time", DESCENDING), ("_id", ASCENDING)])

    # Chats
    db.chats.create_index([("deleted_at", ASCENDING), ("direct", ASCENDING), ("members", ASCENDING)], name="chats_list")
    db.chats.create_index([("invite_code", ASCENDING)], name="invite_codes")

    # Chat messages
    db.chat_messages.create_index([("chat_id", ASCENDING), ("deleted_at", ASCENDING), ("time", DESCENDING), ("_id", ASCENDING)], name="messages_list")
    db.chat_messages.create_index([("chat_id", ASCENDING), ("deleted_at", ASCENDING), ("content", TEXT), ("time", DESCENDING), ("_id", ASCENDING)], name="search")

def reset_cache():
    pass

import pymongo
import pymongo.errors
import redis
import os
import secrets
import time
from radix import Radix
from hashlib import sha256
from base64 import urlsafe_b64encode

from utils import log

CURRENT_DB_VERSION = 10

# Create Redis connection
log("Connecting to Redis...")
try:
    rdb = redis.from_url(os.getenv("REDIS_URI", "redis://127.0.0.1:6379/0"))
except Exception as e:
    log(f"Failed to connect to database! Error: {e}")
    exit()
else:
    log("Successfully connected to Redis!")


# Create database connection
log("Connecting to database...")
try:
    db = pymongo.MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"))[os.getenv("MONGO_DB", "meowerserver")]
    db.command("ping")
except Exception as e:
    log(f"Failed to connect to database! Error: {e}")
    exit()
else:
    log("Successfully connected to database!")


# Create database collections
existing_collections = db.list_collection_names()
for collection_name in []:
    if collection_name not in existing_collections:
        log(f"Creating {collection_name} database collection...")
        db.create_collection(collection_name)

# Create usersv0 indexes
try: db.usersv0.create_index([("lower_username", pymongo.ASCENDING)], name="lower_username", unique=True)
except: pass
try: db.usersv0.create_index([("email", pymongo.ASCENDING)], name="email", unique=True)
except: pass
try: db.usersv0.create_index([("normalized_email_hash", pymongo.ASCENDING)], name="normalized_email_hash", unique=True)
except: pass
try: db.usersv0.create_index([("created", pymongo.DESCENDING)], name="recent_users")
except: pass
try:
    db.usersv0.create_index([
        ("lower_username", pymongo.TEXT),
        ("quote", pymongo.TEXT)
    ], name="search", partialFilterExpression={"pswd": {"$type": "string"}})
except: pass
try: db.usersv0.create_index([
        ("delete_after", pymongo.ASCENDING)
    ], name="scheduled_deletions", partialFilterExpression={"delete_after": {"$type": "number"}})
except: pass

# Create authenticators indexes
try: db.authenticators.create_index([("user", pymongo.ASCENDING)], name="user")
except: pass

# Create account sessions indexes
try: db.acc_sessions.create_index([("user", pymongo.ASCENDING)], name="user")
except: pass
try: db.acc_sessions.create_index([("ip", pymongo.ASCENDING)], name="ip")
except: pass
try: db.acc_sessions.create_index([("refreshed_at", pymongo.ASCENDING)], name="refreshed_at")
except: pass

# Create security log indexes
try: db.security_log.create_index([("user", pymongo.ASCENDING)], name="user")
except: pass

# Create data exports indexes
try: db.data_exports.create_index([("user", pymongo.ASCENDING)], name="user")
except: pass

# Create relationships indexes
try: db.relationships.create_index([("_id.from", pymongo.ASCENDING)], name="from")
except: pass

# Create posts indexes
try:
    db.posts.create_index([
        ("post_origin", pymongo.ASCENDING),
        ("isDeleted", pymongo.ASCENDING),
        ("t.e", pymongo.DESCENDING),
        ("u", pymongo.ASCENDING)
    ], name="default")
except: pass
try:
    db.posts.create_index([
        ("u", pymongo.ASCENDING)
    ], name="user")
except: pass
try:
    db.posts.create_index([
        ("p", pymongo.TEXT)
    ], name="search", partialFilterExpression={"post_origin": "home", "isDeleted": False})
except: pass

try:
    db.posts.create_index([
        ("deleted_at", pymongo.ASCENDING)
    ], name="scheduled_purges", partialFilterExpression={"isDeleted": True, "mod_deleted": False})
except: pass

try:
    db.posts.create_index([
        ("post_origin", pymongo.ASCENDING),
        ("pinned", pymongo.ASCENDING),
        ("t.e", pymongo.DESCENDING)
    ], name="pinned_posts", partialFilterExpression={"pinned": True})
except: pass

# Create post revisions indexes
try:
    db.post_revisions.create_index([
        ("post_id", pymongo.ASCENDING),
        ("time", pymongo.DESCENDING)
    ], name="post_revisions")
except: pass
try:
    db.post_revisions.create_index([
        ("time", pymongo.ASCENDING)
    ], name="scheduled_purges")
except: pass

# Create chats indexes
try:
    db.chats.create_index([
        ("members", pymongo.ASCENDING),
        ("type", pymongo.ASCENDING),
    ], name="user_chats")
except: pass

# Create chat_emojis indexes
try:
    db.chat_emojis.create_index([
        ("chat_id", pymongo.ASCENDING),
    ], name="chat_id")
except: pass

# Create chat_stickers indexes
try:
    db.chat_stickers.create_index([
        ("chat_id", pymongo.ASCENDING),
    ], name="chat_id")
except: pass

# Create reports indexes
try:
    db.reports.create_index([
        ("content_id", pymongo.ASCENDING)
    ], name="pending_reports", partialFilterExpression={"status": "pending"})
except: pass
try:
    db.reports.create_index([
        ("escalated", pymongo.DESCENDING),
        ("reports.time", pymongo.DESCENDING),
        ("status", pymongo.ASCENDING),
        ("type", pymongo.ASCENDING)
    ], name="all_reports")
except: pass

# Create audit log indexes
try:
    db.audit_log.create_index([
        ("time", pymongo.ASCENDING),
        ("type", pymongo.ASCENDING)
    ], name="scheduled_purges")
except: pass

# Create post reactions index
try:
    db.post_reactions.create_index([("_id.post_id", 1), ("_id.emoji", 1)])
except: pass


# Create default database items
try:
    db.config.insert_one({
        "_id": "migration",
        "database": 1
    })
except pymongo.errors.DuplicateKeyError: pass
try:
    db.config.insert_one({
        "_id": "status",
        "repair_mode": False,
        "registration": True
    })
except pymongo.errors.DuplicateKeyError: pass
try:
    db.config.insert_one({
        "_id": "signing_keys",
        "acc": secrets.token_bytes(64),
        "email": secrets.token_bytes(64)
    })
except pymongo.errors.DuplicateKeyError: pass


# Load signing keys
signing_keys = db.config.find_one({"_id": "signing_keys"})


# Load netblocks
blocked_ips = Radix()
registration_blocked_ips = Radix()
for netblock in db.netblock.find({}):
    try:
        if netblock["type"] == 0:
            blocked_ips.add(netblock["_id"])
        if netblock["type"] == 1:
            registration_blocked_ips.add(netblock["_id"])
    except Exception as e:
        log(f"Failed to load netblock {netblock['_id']}: {e}")
log(f"Successfully loaded {len(blocked_ips.nodes())} netblock(s) into Radix!")
log(f"Successfully loaded {len(registration_blocked_ips.nodes())} registration netblock(s) into Radix!")


def get_total_pages(collection: str, query: dict, page_size: int = 25) -> int:
    item_count = db[collection].count_documents(query)
    pages = (item_count // page_size)
    if (item_count % page_size) > 0:
        pages += 1
    return pages

if db.config.find_one({"_id": "migration", "database": {"$ne": CURRENT_DB_VERSION}}):
    log(f"[Migrator] Migrating DB to version {CURRENT_DB_VERSION}. ")
    log(f"[Migrator] Please do not shut the server down until it is done.")

    # Chat pinning
    log("[Migrator] Adding pinned messages to database")
    db.posts.update_many({"pinned": {"$exists": False}}, {"$set": {"pinned": False}})

    log("[Migrator] Adding perm for pinning posts")
    db.chats.update_many({"allow_pinning": {"$exists": False}}, {"$set": {"allow_pinning": False}})

    # Experiments
    log("[Migrator] Removing experiments from database")
    db.usersv0.update_many({"experiments": {"$exists": True}}, {"$unset": {"experiments": ""}})

    # Custom profile pictures
    log("[Migrator] Adding custom profile pictures to database")
    db.usersv0.update_many({"pswd": {"$ne": None}, "avatar": {"$exists": False}}, {"$set": {"avatar": ""}})
    db.usersv0.update_many({"pswd": {"$ne": None}, "avatar_color": {"$exists": False}}, {"$set": {"avatar_color": "000000"}})

    # Chat icons
    log("[Migrator] Adding chat icons to database")
    db.chats.update_many({"icon": {"$exists": False}}, {"$set": {"icon": ""}})
    db.chats.update_many({"icon_color": {"$exists": False}}, {"$set": {"icon_color": "000000"}})

    # Post attachments
    log("[Migrator] Adding post attachments to database")
    db.posts.update_many({"attachments": {"$exists": False}}, {"$set": {"attachments": []}})

    # Profanity filter
    log("[Migrator] Removing profanity filter")
    db.config.delete_one({"_id": "filter"})
    db.posts.update_many({"unfiltered_p": {"$exists": True}}, [{"$set": {"p": "$unfiltered_p"}}])
    db.posts.update_many({"unfiltered_p": {"$exists": True}}, {"$unset": {"unfiltered_p": ""}})

    # MFA recovery codes
    log("[Migrator] Adding MFA recovery codes")
    for user in db.usersv0.find({"pswd": {"$ne": None}, "mfa_recovery_code": {"$exists": False}}, projection={"_id": 1}):
        db.usersv0.update_one({"_id": user["_id"]}, {"$set": {
            "mfa_recovery_code": secrets.token_hex(5)
        }})
    
    # Post reactions
    log("[Migrator] Adding post reactions to database")
    db.posts.update_many({"reactions": {"$exists": False}}, {"$set": {"reactions": []}})

    # Remove type and post_id fields in posts database
    log("[Migrator] Removing type and post_id fields from posts database")
    db.posts.update_many({}, {"$unset": {"type": "", "post_id": ""}})

    # Post replies
    log("[Migrator] Adding post replies to database")
    db.posts.update_many({"reply_to": {"$exists": False}}, {"$set": {"reply_to": []}})

    # Fix MFA recovery codes
    log("[Migrator] Fixing MFA recovery codes")
    for user in db.usersv0.aggregate([
        {"$match": {"mfa_recovery_code": {"$ne": None}}},
        {"$project": {
            "mfa_recovery_code": 1,
            "length": {"$strLenCP": "$mfa_recovery_code"}
        }},
        {"$match": {
            "length": {"$gt": 10}
        }}
    ]):
        db.usersv0.update_one({"_id": user["_id"]}, {"$set": {
            "mfa_recovery_code": user["mfa_recovery_code"][:10]
        }})

    # Delete system users from DB
    log("[Migrator] Deleting system users from DB")
    db.usersv0.delete_many({"_id": {"$in": ["Server", "Deleted", "Meower", "Admin", "username"]}})

    # Emails
    log("[Migrator] Adding email addresses")
    db.usersv0.update_many({"email": {"$exists": False}}, {"$set": {
        "email": "",
        "normalized_email_hash": ""
    }})

    # New sessions
    log("[Migrator] Adding new sessions")
    for user in db.usersv0.find({
        "tokens": {"$exists": True},
        "last_seen": {"$ne": None, "$gt": int(time.time())-(86400*21)},
    }, projection={"_id": 1, "tokens": 1}):
        if user["tokens"]:
            for token in user["tokens"]:
                rdb.set(
                    urlsafe_b64encode(sha256(token.encode()).digest()),
                    user["_id"],
                    ex=86400*21  # 21 days
                )
    db.usersv0.update_many({}, {"$unset": {"tokens": ""}})
    try: db.usersv0.drop_index("tokens")
    except: pass

    # No more netinfo and netlog
    log("[Migrator] Removing netinfo and netlog")
    db.netinfo.drop()
    db.netlog.drop()

    db.config.update_one({"_id": "migration"}, {"$set": {"database": CURRENT_DB_VERSION}})
    log(f"[Migrator] Finished Migrating DB to version {CURRENT_DB_VERSION}")

print("") # finished startup logs

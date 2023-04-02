from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from redis import Redis
import os
import secrets

from src.common.util import config, logging, migration


DB_COLLECTIONS = {
    "config",
    "users",
    "networks",
    "posts",
    "chats",
    "reports",
    "audit_log"
}
DB_VERSION = 2


def create_collections():
    existing_collections = set(db.list_collection_names())
    for collection in DB_COLLECTIONS:
        if collection not in existing_collections:
            logging.info(f"Creating collection {collection}...")
            db.create_collection(collection)


def delete_indexes():
    logging.info("Deleting indexes...")
    for collection in db.list_collection_names():
        db[collection].drop_indexes()


def build_indexes():
    logging.info("Building indexes...")

    # Users
    db.users.create_index([("lower_username", ASCENDING)], name="username",
                          unique=True)
    db.users.create_index([("lower_username", TEXT), ("created", DESCENDING)],
                          name="search")

    # Networks
    db.networks.create_index([("users", ASCENDING)], name="users")
    db.networks.create_index([("last_used", ASCENDING)],
                             name="inactive_networks",
                             expireAfterSeconds=7776000,
                             partialFilterExpression={"banned": False})

    # Posts
    db.posts.create_index([("origin", ASCENDING), ("deleted_at", ASCENDING),
                           ("author", ASCENDING), ("time", DESCENDING)],
                           name="existing_posts",
                           partialFilterExpression={"deleted_at": None})
    db.posts.create_index([("origin", ASCENDING), ("deleted_at", ASCENDING),
                           ("content", TEXT), ("time", DESCENDING)],
                           name="search",
                           partialFilterExpression={"deleted_at": None})
    db.posts.create_index([("origin", ASCENDING), ("deleted_at", ASCENDING),
                           ("time", DESCENDING), ("author", ASCENDING)],
                           name="inbox",
                           partialFilterExpression={"origin": "inbox", "deleted_at": None})
    db.posts.create_index([("deleted_at", ASCENDING)], name="deleted_posts",
                          expireAfterSeconds=2592000,
                          partialFilterExpression={"deleted_at": {"$exists": True}})

    # Chats
    db.chats.create_index([("members", ASCENDING), ("created", DESCENDING)],
                          name="user_chats")
    db.chats.create_index([("invite_code", ASCENDING)], name="invite_code")

    # Reports
    db.reports.create_index([("reputation", DESCENDING)],
                            name="report_reputation")

    # Audit log
    db.audit_log.create_index([("time", DESCENDING)], name="logs",
                              expireAfterSeconds=2592000)


def create_config_items():
    logging.info("Creating config items...")
    db.config.insert_one({"_id": "version", "database": DB_VERSION})
    db.config.insert_one({"_id": "security", "signing_key": secrets.token_bytes(2048)})
    db.config.insert_one({"_id": "filter", "whitelist": [], "blacklist": []})


def setup_db():
    # Detect current database version
    logging.info("Detecting database version...")
    db_version = db.config.find_one({"_id": "version"})
    if db_version:
        db_version = db_version.get("database")
    elif len(db.list_collection_names()) > 0:
        db_version = 1
    elif "Meower" in os.listdir():
        db_version = 0
    else:
        create_collections()
        delete_indexes()
        create_config_items()
        build_indexes()
        db_version = DB_VERSION

    # Make sure DB version exists
    if db_version <= DB_VERSION:
        logging.info(f"Database v{db_version} detected!")
    else:
        logging.error("Unknown databse version!")
        logging.error("The database was probably created in a newer server build.")
        logging.error("Exiting...")
        exit()

    # Migrate database (if required)
    if db_version < DB_VERSION:
        logging.info("Migrating database...")
        logging.warn("Please be patient and do not stop the server!")
        if db_version == 0:
            delete_indexes()
            migration.migrate_from_v0(db)
            build_indexes()
        elif db_version == 1:
            delete_indexes()
            migration.migrate_from_v1(db)
            build_indexes()

    # Set DB version
    if db.config.count_documents({"_id": "version"}) > 0:
        db.config.update_one({"_id": "version"}, {"$set": {"database": DB_VERSION}})
    else:
        db.config.insert_one({"_id": "version", "database": DB_VERSION})


def count_pages(collection: str, query: dict) -> int:
    total_items = db[collection].count_documents(query)
    if total_items == 0:
        pages = 0
    else:
        if (total_items % 25) == 0:
            if (total_items < 25):
                pages = 1
            else:
                pages = (total_items // 25)
        else:
            pages = (total_items // 25)+1

    return pages


# Connect to MongoDB
try:
    db = MongoClient(config.db_uri)[config.db_name]
    db.command("ping")
except Exception as e:
    logging.error(f"Failed connecting to database: {str(e)}")
    exit()


# Connect to Redis
try:
    redis = Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        password=config.redis_password
    )
except Exception as e:
    logging.error(f"Failed connecting to Redis: {str(e)}")
    exit()


# Setup database
setup_db()

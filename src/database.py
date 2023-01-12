from pymongo import MongoClient
from redis import Redis
import os

from src.util import logging

# Connect to MongoDB
try:
    db = MongoClient(os.getenv("DB_URI", "mongodb://127.0.0.1:27017"))[os.getenv("DB_NAME", "meowercl4")]
except Exception as err:
    logging.error("Failed connecting to database: {0}".format(err))

# Connect to Redis
try:
    redis = Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        password=os.getenv("REDIS_PASSWORD")
    )
except Exception as err:
    logging.error("Failed connecting to Redis: {0}".format(err))

import os
import shutil

from src.util import uid
from src.database import db, redis

def create_backup():
    name = f"backup-"

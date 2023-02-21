from datetime import datetime
from hashlib import sha256
from secrets import token_urlsafe
from sys import getsizeof
import zlib
import os
import time

from src.util import status, uid, bitfield, flags
from src.entities import users, infractions
from src.database import db

class File:
    def __init__(
        self,
        _id: str,
        mime_type: str = None,
        size: int = None,
        data: bytes = None,
        status: int = None,
        created: datetime = None
    ):
        self.hash = _id
        self.mime_type = mime_type
        self.size = size
        self.data = zlib.decompress(data)
        self.status = status
        self.created = created

    def block(self, blank_data: bool = False, poisonous: bool = False):
        """
        0: normal
        1: blocked
        2: blocked & poisonous
        """

        # Blank data
        if blank_data:
            self.data = None
            db.files.update_one({"_id": self.hash}, {"$set": {"data": None}})

        # Set block status
        self.status = (2 if poisonous else 1)
        db.files.update_one({"_id": self.hash}, {"$set": {"status": self.status}})

    def unblock(self):
        # Destroy file if data cannot be recovered
        if not self.data:
            db.files.delete_one({"_id": self.hash})

        # Set block status
        self.status = 0
        db.files.update_one({"_id": self.hash}, {"$set": {"status": self.status}})

    def delete(self):
        db.files.delete_one({"_id": self.hash})

class Upload:
    def __init__(
        self,
        _id: str,
        token: str = None,
        uploader: str = None,
        filename: str = None,
        file_hash: str = None,
        created: datetime = None
    ):
        self.id = _id
        self.token = token
        self.uploader = users.get_user(uploader)
        self.filename = filename
        self.file_hash = file_hash
        self.created = created

    @property
    def link(self):
        return (os.getenv("API_DOMAIN", "https://api.meower.org/") + f"v1/uploads/{self.id}/{self.token}")

    @property
    def file(self):
        return get_file(self.file_hash)

    def delete(self):
        db.uploads.delete_one({"_id": self.id})

def get_or_create_file(mime_type: str, data: bytes):
    # Get file hash
    hash = sha256(data).hexdigest()

    # Check if file already exists
    file = db.files.find_one({"_id": hash})
    if file:
        return File(**file)

    # Get file size
    file_size = getsizeof(data)

    # Check file size (before compression)
    if file_size > int(os.getenv("UPLOAD_LIMIT", 10000000)):
        raise status.fileTooLarge

    # Compress data
    compressed_data = zlib.compress(data)

    # Check file size
    if getsizeof(compressed_data) > int(os.getenv("UPLOAD_LIMIT", 5000000)):
        raise status.fileTooLarge

    # Create file
    file = {
        "_id": hash,
        "mime_type": mime_type,
        "size": file_size,
        "data": compressed_data,
        "status": 0,
        "created": uid.timestamp()
    }
    db.files.insert_one(file)

    # Return file
    return File(**file)

def create_upload(uploader: any, filename: str, mime_type: str, data: bytes):
    # Create token
    token = token_urlsafe(32)

    # Get/create file
    file = get_or_create_file(mime_type, data)

    # Check whether file is blocked
    if file.status != 0:
        if file.status == 2:
            infractions.create_infraction(
                uploader,
                users.get_user("0"),
                1,
                "Attempting to upload files that are against the Terms of Service.",
                flags=bitfield.create([flags.infractions.automatic])
            )
        raise status.missingPermissions

    # Create upload
    upload = {
        "_id": uid.snowflake(),
        "token": token,
        "uploader": uploader.id,
        "filename": filename,
        "file_hash": file.hash,
        "created": uid.timestamp()
    }
    db.uploads.insert_one(upload)
    return Upload(**upload)

def get_file(file_hash: str):
    file = db.files.find_one({"_id": file_hash})
    if not file:
        raise status.resourceNotFound

    return File(**file)

def get_upload(upload_id: str):
    upload = db.uploads.find_one({"_id": upload_id})
    if not upload:
        raise status.resourceNotFound

    return Upload(**upload)

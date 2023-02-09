from datetime import datetime
from hashlib import sha256
from secrets import token_urlsafe
from sys import getsizeof
import zlib
import os

from src.util import status, uid
from src.entities import users
from src.database import db

class Upload:
    def __init__(
        self,
        _id: str,
        uploaded_by: list = [],
        tokens: list = [],
        flags: int = 0,
        filename: str = None,
        mime_type: str = None,
        size: int = None,
        data: bytes = None,
        created: datetime = None
    ):
        self.id = _id
        self.uploaded_by = [users.get_user(user_id) for user_id in uploaded_by]
        self.tokens = tokens
        self.flags = flags
        self.filename = filename
        self.mime_type = mime_type
        self.size = size
        self.data = zlib.decompress(data)
        self.created = created

    @property
    def metadata(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size": self.size,
            "link": "",
            "created": int(self.created.timestamp())
        }

    def add_token(self, uploader: users.User, token: str):
        self.uploaded_by.append(uploader)
        self.tokens.append(token)
        db.uploads.update_one({"_id": self.id}, {"$addToSet": {
            "uploaded_by": uploader.id,
            "tokens": token
        }})

def create_upload(uploader: users.User, filename: str, mime_type: str, data: bytes):
    # Create upload hash and token
    hash = sha256(data).hexdigest()
    token = token_urlsafe(16)

    # Check if upload already exists
    upload = db.uploads.find_one({"_id": hash})
    if upload:
        upload = Upload(**upload)
        upload.add_token(uploader, token)
        return upload

    # Get file size
    file_size = getsizeof(data)

    # Compress data
    data = zlib.compress(data)

    # Check file size
    if getsizeof(data) > int(os.getenv("UPLOAD_LIMIT", 5000000)):
        raise status.missingPermissions  # placeholder

    # Check MIME type
    if mime_type not in [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp"
    ]:
        raise status.missingPermissions  # placeholder

    # Store new upload
    upload = {
        "_id": hash,
        "uploaded_by": [uploader.id],
        "tokens": [token],
        "flags": 0,
        "filename": filename,
        "mime_type": mime_type,
        "size": file_size,
        "data": data,
        "created": uid.timestamp()
    }
    db.uploads.insert_one(upload)
    return Upload(**upload)

def get_upload(hash: str):
    upload = db.uploads.find_one({"_id": hash})
    if not upload:
        raise status.notFound

    return Upload(**upload)

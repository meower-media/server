from quart import Blueprint, current_app as app, request, abort
from pydantic import BaseModel
from typing import Literal
import os

from security import UserFlags, Restrictions


uploads_bp = Blueprint("uploads_bp", __name__, url_prefix="/uploads")


@uploads_bp.get("/<upload_type>/token")
async def request_upload_token(upload_type: Literal["icons", "attachments"]):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if app.supporter.ratelimited(f"uploads:{request.user}"):
        abort(429)

    # Ratelimit
    app.supporter.ratelimit(f"uploads:{request.user}", 10, 15)

    # Check restrictions
    if app.security.is_restricted(request.user, Restrictions.UPLOADING_FILES):
        return {"error": True, "type": "accountBanned"}, 403
    
    # Check type
    if upload_type == "icons":
        pass
    elif upload_type == "attachments":
        if not ((request.flags & UserFlags.CAN_UPLOAD_ATTACHMENTS) == UserFlags.CAN_UPLOAD_ATTACHMENTS):
            abort(403)
    else:
        abort(400)

    # Get URL
    url = os.getenv("UPLOADS_URL")
    if not url:
        abort(503)
    if not url.endswith("/"):
        url += "/"
    url += upload_type

    # Get max size
    if upload_type == "icons":
        max_size = (4 << 20)  # 4 MiB
    elif upload_type == "attachments":
        max_size = (25 << 20)  # 25 MiB
    else:
        max_size = 0

    # Create token
    token, expires_at = app.supporter.create_uploads_token(upload_type, request.user, max_size)

    # Return URL, token, and token expiration
    return {
        "error": False,
        "url": url,
        "token": token,
        "expires_at": expires_at
    }, 200

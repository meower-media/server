from quart import Blueprint, current_app as app, request, abort
from secrets import token_urlsafe
import os

import security


uploads_bp = Blueprint("uploads_bp", __name__, url_prefix="/uploads")


@uploads_bp.get("/token/<upload_type>")
async def get_uploads_token(upload_type):
    # Check authorization
    if not request.user:
        abort(401)

    # Check type and get max size
    match upload_type:
        case "icon":
            max_size = (5 << 20)  # 5 MiB
        case "attachment":
            # Check experiments
            if not (request.experiments & security.UserExperiments.POST_ATTACHMENTS):
                abort(403)

            max_size = (25 << 20)  # 25 MiB
        case _:
            abort(404)
    
    # Generate upload ID
    upload_id = token_urlsafe(18).replace("-", "a").replace("_", "b").replace("=", "c")

    # Generate token
    token, expires = security.create_token("upload_" + upload_type, 900, {
        "id": upload_id,
        "u": request.user,
        "s": max_size
    })

    return {
        "error": False,
        "id": upload_id,
        "expires": expires,
        "max_size": max_size,
        "token": token
    }, 200

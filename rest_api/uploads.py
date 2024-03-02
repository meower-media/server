from quart import Blueprint, current_app as app, request, abort
import os

import security


uploads_bp = Blueprint("uploads_bp", __name__, url_prefix="/uploads")


@uploads_bp.get("/<upload_type>")
async def get_uploads_token(upload_type):
    # Make sure there's an uploads token secret
    if "UPLOADS_TOKEN_SECRET" not in os.environ:
        abort(404)

    # Check authorization
    if not request.user:
        abort(401)
    
    # Check restrictions
    if security.is_restricted(request.user, security.Restrictions.HOME_POSTS):
        return {"error": True, "type": "accountBanned"}, 403

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
    
    # Generate token
    upload_id, expires, token = app.supporter.create_uploads_token(upload_type, request.user, max_size)

    return {
        "error": False,
        "id": upload_id,
        "expires": expires,
        "max_size": max_size,
        "token": token
    }, 200

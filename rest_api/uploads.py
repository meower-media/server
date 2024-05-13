from quart import Blueprint, request, abort
from quart_schema import deprecate


uploads_bp = Blueprint("uploads_bp", __name__, url_prefix="/uploads")


@uploads_bp.get("/token/icon")
@deprecate()
async def deprecated_get_icon_uploads_token():
    # Check authorization
    if not request.user:
        abort(401)

    return {
        "error": False,
        "id": None,
        "expires": None,
        "max_size": (5 << 20),
        "token": request.headers.get("token")
    }, 200

from quart import Quart, request, abort
from quart_cors import cors
from quart_schema import QuartSchema, RequestSchemaValidationError, validate_headers, hide
from pydantic import BaseModel
import time, os, msgpack

from .v0 import v0


from .admin import admin_bp

from database import db, rdb, blocked_ips, registration_blocked_ips
import security


# Init app
app = Quart(__name__)
app.config["APPLICATION_ROOT"] = os.getenv("API_ROOT", "")
app.url_map.strict_slashes = False
cors(app, allow_origin="*")
QuartSchema(app)


class TokenHeader(BaseModel):
    token: str | None = None
    username: str | None = None


@app.before_request
async def check_repair_mode():
    if app.supporter.repair_mode and request.path != "/status":
        return {"error": True, "type": "repairModeEnabled"}, 503


@app.before_request
async def internal_auth():
    if "Cf-Connecting-Ip" not in request.headers:  # Make sure there's no Cf-Connecting-Ip header
        if request.headers.get("X-Internal-Token") == os.getenv("INTERNAL_API_TOKEN"):  # Check internal token
            # Safety check
            if os.getenv("INTERNAL_API_TOKEN") == "" and request.remote_addr != "127.0.0.1":
                abort(401)

            request.internal_ip = request.headers.get("X-Internal-Ip")
            request.internal_username = request.headers.get("X-Internal-Username")
            request.bypass_captcha = True


@app.before_request
async def check_ip():
    if hasattr(request, "internal_ip") and request.internal_ip:  # internal IP forwarding
        request.ip = request.internal_ip
    else:
        request.ip = (request.headers.get("Cf-Connecting-Ip", request.remote_addr))
    if request.path != "/status" and blocked_ips.search_best(request.ip):
        return {"error": True, "type": "ipBlocked"}, 403


@app.before_request
@validate_headers(TokenHeader)
async def check_auth(headers: TokenHeader):
    # Init request user and permissions
    request.user = None
    request.permissions = 0

    # Authenticate request
    account = None
    if request.path != "/status":
        if hasattr(request, "internal_username") and request.internal_username:  # internal auth
            account = db.usersv0.find_one({"_id": request.internal_username}, projection={
                "_id": 1,
                "uuid": 1,
                "flags": 1,
                "permissions": 1,
                "ban.state": 1,
                "ban.expires": 1
            })
        elif headers.token:  # external auth
            account = db.usersv0.find_one({"tokens": headers.token}, projection={
                "_id": 1,
                "uuid": 1,
                "flags": 1,
                "permissions": 1,
                "ban.state": 1,
                "ban.expires": 1
            })
        
        if account:
            if account["ban"]["state"] == "perm_ban" or (account["ban"]["state"] == "temp_ban" and account["ban"]["expires"] > time.time()):
                rdb.publish("admin", msgpack.packb({
                    "op": "log",
                    "data": f"**Banned (REST API)**\n@{account['_id']} ({account['uuid']})\nInternal username: {getattr(request, "internal_username")}\nBan: {account['ban']}"
                }))
                return {"error": True, "type": "accountBanned"}, 403
            request.user = account["_id"]
            request.flags = account["flags"]
            request.permissions = account["permissions"]


@app.get("/")  # Welcome message
async def index():
    return {
        "captcha": {
            "enabled": os.getenv("CAPTCHA_SECRET") is not None,
            "sitekey": os.getenv("CAPTCHA_SITEKEY")
        }
    }, 200


@app.get("/favicon.ico")  # Favicon, my ass. We need no favicon for an API.
@hide
async def favicon_my_ass():
    return "", 200


@app.get("/status")
async def get_status():
    return {
        "scratchDeprecated": True,
        "registrationEnabled": app.supporter.registration,
        "isRepairMode": app.supporter.repair_mode,
        "ipBlocked": (blocked_ips.search_best(request.ip) is not None),
        "ipRegistrationBlocked": (registration_blocked_ips.search_best(request.ip) is not None)
    }, 200


@app.get("/statistics")
async def get_statistics():
    return {
        "error": False,
        "users": db.usersv0.estimated_document_count(),
        "posts": db.posts.estimated_document_count(),
        "chats": db.chats.estimated_document_count()
    }, 200


@app.get("/ulist")
async def get_ulist():
    # Get page
    try:
        page = int(request.args["page"])
    except:
        page = 1

    # Get online usernames
    usernames = list(app.cl.usernames.keys())

    # Get total pages
    pages = (len(usernames) // 25)
    if (len(usernames) % 25) > 0:
        pages += 1

    # Truncate list
    usernames = usernames[((page-1)*25):(((page-1)*25)+25)]

    # Return users
    return {
        "error": False,
        "autoget": [security.get_account(username) for username in usernames],
        "page#": page,
        "pages": pages
    }, 200


@app.errorhandler(RequestSchemaValidationError)
async def validation_error(e):
    return {"error": True, "type": "badRequest"}, 400


@app.errorhandler(400)  # Bad request
async def bad_request(e):
    return {"error": True, "type": "badRequest"}, 400


@app.errorhandler(401)  # Unauthorized
async def unauthorized(e):
    return {"error": True, "type": "Unauthorized"}, 401


@app.errorhandler(403)  # Missing permissions
async def missing_permissions(e):
    return {"error": True, "type": "missingPermissions"}, 403


@app.errorhandler(404)  # We do need a 404 handler.
async def not_found(e):
    return {"error": True, "type": "notFound"}, 404


@app.errorhandler(405)  # Method not allowed
async def method_not_allowed(e):
    return {"error": True, "type": "methodNotAllowed"}, 405


@app.errorhandler(429)  # Too many requests
async def too_many_requests(e):
    return {"error": True, "type": "tooManyRequests"}, 429


@app.errorhandler(500)  # Internal
async def internal(e):
    return {"error": True, "type": "Internal"}, 500


@app.errorhandler(501)  # Not implemented
async def not_implemented(e):
      return {"error": True, "type": "notImplemented"}, 501


# Register blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(v0, url_prefix="/v0")
app.register_blueprint(v0, url_prefix="/", name="root")
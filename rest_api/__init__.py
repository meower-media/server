from flask import Flask, request, abort
from flask_cors import CORS
import time

from .home import home_bp
from .inbox import inbox_bp
from .posts import posts_bp
from .users import users_bp
from .chats import chats_bp
from .search import search_bp
from .admin import admin_bp


# Init app
app = Flask(__name__, static_folder="static")
cors = CORS(app, resources=r'*', origins=r'*', allow_headers=r'*', max_age=86400)


@app.before_request
def check_repair_mode():
    if request.path != "/" and request.path != "/status":
        if app.supporter.repair_mode:
            return {"error": True, "type": "repairModeEnabled"}, 503


@app.before_request
def check_ip():
    request.ip = (request.headers.get("Cf-Connecting-Ip", request.remote_addr))
    if request.path != "/" and request.path != "/status":
        if app.supporter.blocked_ips.search_best(request.ip):
            return {"error": True, "type": "ipBlocked"}, 403


@app.before_request
def check_auth():
    request.user = None
    request.permissions = 0

    if ("username" in request.headers) and ("token" in request.headers):
        # Get username and token
        username = request.headers.get("username")
        token = request.headers.get("token")
        if not (len(username) < 1 or len(username) > 20 or len(token) < 1 or len(token) > 100):
            # Authenticate request
            account = app.files.db.usersv0.find_one({"lower_username": username.lower()}, projection={
                "_id": 1,
                "tokens": 1,
                "permissions": 1,
                "ban": 1
            })
            if account and account["tokens"] and (token in account["tokens"]):
                if account["ban"]["state"] == "PermBan" or (account["ban"]["state"] == "TempBan" and account["ban"]["expires"] > time.time()):
                    abort(401)
                request.user = account["_id"]
                request.permissions = account["permissions"]


@app.route('/', methods=['GET'])  # Welcome message
def index():
	return "Hello world! The Meower API is working, but it's under construction. Please come back later.", 200


@app.route('/ip', methods=['GET'])  # Deprecated
def ip_tracer():
	return "", 410


@app.route('/favicon.ico', methods=['GET']) # Favicon, my ass. We need no favicon for an API.
def favicon_my_ass():
	return "", 200


@app.route('/status', methods=["GET"])
def get_status():
    return {
        "scratchDeprecated": True,
        "registrationEnabled": app.supporter.registration,
        "isRepairMode": app.supporter.repair_mode,
        "ipBlocked": (app.supporter.blocked_ips.search_best(request.ip) is not None),
        "ipRegistrationBlocked": (app.supporter.registration_blocked_ips.search_best(request.ip) is not None)
    }, 200


@app.route('/statistics', methods=["GET"])
def get_statistics():
    return {
        "error": False,
        "users": app.files.db.usersv0.estimated_document_count(),
        "posts": app.files.db.posts.estimated_document_count(),
        "chats": app.files.db.chats.estimated_document_count()
    }, 200


@app.errorhandler(400)  # Bad request
def bad_request(e):
	return {"error": True, "type": "badRequest"}, 400


@app.errorhandler(401)  # Unauthorized
def unauthorized(e):
	return {"error": True, "type": "Unauthorized"}, 401


@app.errorhandler(403)  # Missing permissions
def missing_permissions(e):
    return {"error": True, "type": "missingPermissions"}, 403


@app.errorhandler(404)  # We do need a 404 handler.
def not_found(e):
	return {"error": True, "type": "notFound"}, 404


@app.errorhandler(405)  # Method not allowed
def method_not_allowed(e):
	return {"error": True, "type": "methodNotAllowed"}, 405


@app.errorhandler(429)  # Too many requests
def too_many_requests(e):
	return {"error": True, "type": "tooManyRequests"}, 429


@app.errorhandler(500)  # Internal
def internal(e):
	return {"error": True, "type": "Internal"}, 500


# Register blueprints
app.register_blueprint(home_bp)
app.register_blueprint(inbox_bp)
app.register_blueprint(posts_bp)
app.register_blueprint(users_bp)
app.register_blueprint(chats_bp)
app.register_blueprint(search_bp)
app.register_blueprint(admin_bp)
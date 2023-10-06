from flask import Flask, request, abort
from flask_cors import CORS
import pymongo
import time

from security import DEFAULT_USER_SETTINGS, Permissions


# Init app
app = Flask(__name__, static_folder="static")
cors = CORS(app, resources=r'*', origins=r'*', allow_headers=r'*', max_age=86400)


@app.before_request
def pre_request_check_auth():
    request.ip = (request.headers.get("Cf-Connecting-Ip", request.remote_addr))

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
            if account and (token in account["tokens"]):
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
    status = app.files.db.config.find_one({"_id": "status"})
    return {
        "isRepairMode": status["repair_mode"],
        "scratchDeprecated": True,
        "registrationDisabled": status["registration_disabled"]
    }, 200


@app.route('/statistics', methods=["GET"])
def get_statistics():
    return {
        "error": False,
        "users": app.files.db.usersv0.estimated_document_count(),
        "posts": app.files.db.posts.estimated_document_count(),
        "chats": app.files.db.chats.estimated_document_count()
    }, 200


@app.route('/home', methods=["GET"])
def get_home_posts():
    # Get page
    page = 1
    if request.user:
        try:
            page = int(request.args["page"])
        except: pass

    # Get posts
    query = {"post_origin": "home", "isDeleted": False}
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": (app.files.get_total_pages("posts", query) if request.user else 1)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@app.route('/inbox', methods=["GET"])
def get_inbox_posts():
    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Check authorization
    if not request.user:
        abort(401)

    # Get posts
    query = {"post_origin": "inbox", "isDeleted": False, "u": {"$in": [request.user, "Server"]}}
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("posts", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@app.route('/posts/<chatid>', methods=["GET"])
def get_chat_posts(chatid):
    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Check authorization
    if request.user is None:
        abort(401)

    # Get chat
    chat = app.files.db.chats.find_one({"_id": chatid})
    if not chat:
        abort(404)
    
    # Check permissions
    can_view_all_chats = app.security.has_permission(request.permissions, Permissions.VIEW_CHATS)
    if not can_view_all_chats:
        if chat["deleted"]:
            abort(404)
        elif request.user not in chat["members"]:
            abort(404)

    # Get posts
    query = {"post_origin": chatid, "isDeleted": False}
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("posts", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@app.route('/posts', methods = ["GET"])
def get_post():
    # Get post ID
    post_id = request.args.get("id")
    if not post_id:
        return {"error": True, "type": "noQueryString"}, 400
    
    # Get post
    post = app.files.db.posts.find_one({"_id": post_id})
    if not post:
        abort(404)

    # Check permissions
    can_view_all_posts = app.security.has_permission(request.permissions, Permissions.VIEW_POSTS)
    if not can_view_all_posts:
        if post["isDeleted"]:
            abort(404)
        elif (post["post_origin"] == "inbox") and (post["u"] != request.user):
            abort(404)
        elif post["post_origin"] != "home":
            chat = app.files.db.chats.find_one({"_id": post["post_origin"]})
            if (not chat) or chat["deleted"] or (request.user not in chat["members"]):
                abort(404)

    # Return post
    post["error"] = False
    return post, 200


@app.route('/users/<username>', methods=["GET"])
def get_user(username):
    account = app.security.get_account(username, (request.user and request.user.lower() == username.lower()))
    if account:
        account["error"] = False
        return account, 200
    else:
        abort(404)


@app.route('/users/<username>/posts', methods=["GET"])
def get_user_posts(username):
    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Get posts
    query = {"post_origin": "home", "isDeleted": False, "u": username}
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("posts", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@app.route('/search/home', methods=["GET"])
def search_home():
    # Get query
    q = request.args.get("q")
    if not q:
        return {"error": True, "type": "noQueryString"}, 400
    elif len(q) > 4000:
        q = q[:4000]

    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Get posts
    query = {"post_origin": "home", "isDeleted": False, "$text": {"$search": q}}
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("posts", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@app.route('/search/users', methods=["GET"])
def search_users():
    # Get query
    q = request.args.get("q")
    if not q:
        return {"error": True, "type": "noQueryString"}, 400
    elif len(q) > 20:
        q = q[:20]

    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Get users
    query = {"lower_username": {"$regex": q}}
    usernames = [user["_id"] for user in app.files.db.usersv0.find(query, projection={
        "_id": 1
    }, skip=(page-1)*25, limit=25)]

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("usersv0", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = [app.security.get_account(username) for username in usernames]
    else:
        payload["index"] = usernames
    return payload, 200


"""
@app.route('/admin/pending-reports', methods=["GET"])
def get_pending_reports():
    if not app.security.has_permission(request.permissions, Permissions.VIEW_REPORTS):
        abort(401)

    page = 1
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 400

    reports = meower.getIndex(location="reports", query={"status": {"$lt": 2}}, truncate=True, sort="_id", page=page)

    payload = {"error": False, "reports": [], "page#": reports["page#"], "pages": reports["pages"]}
    for report in reports["index"]:
        if report["type"] == 0:
            fileread, filedata = app.files.load_item("posts", report["content_id"])
            if not fileread:
                app.files.delete_item("reports", report["_id"])
                continue
        elif report["type"] == 1:
            filecheck, fileget, filedata = app.security.get_account(report["content_id"], True, True)
            if not (filecheck and fileget):
                app.files.delete_item("reports", report["_id"])
                continue
        else:
            app.files.delete_item("reports", report["_id"])
            continue

        report.update({"content": filedata})
        payload["reports"].append(report)
    
    return payload, 200


@app.route('/admin/completed-reports', methods=["GET"])
def get_completed_reports():
    if not app.security.has_permission(request.permissions, Permissions.VIEW_REPORTS):
        abort(401)

    page = 1
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 400

    reports = meower.getIndex(location="reports", query={"status": {"$lt": 2}}, truncate=True, sort="_id", page=page)

    payload = {"error": False, "reports": [], "page#": reports["page#"], "pages": reports["pages"]}
    for report in reports["index"]:
        if report["type"] == 0:
            fileread, filedata = app.files.load_item("posts", report["content_id"])
            if not fileread:
                app.files.delete_item("reports", report["_id"])
                continue
        elif report["type"] == 1:
            filecheck, fileget, filedata = app.security.get_account(report["content_id"], True, True)
            if not (filecheck and fileget):
                app.files.delete_item("reports", report["_id"])
                continue
        else:
            app.files.delete_item("reports", report["_id"])
            continue

        report.update({"content": filedata})
        payload["reports"].append(report)
    
    return payload, 200
"""


@app.route("/admin/notes/<identifier>", methods=["GET", "PUT"])
def admin_notes(identifier):
    if request.method == "GET":
        if not app.security.has_permission(request.permissions, Permissions.VIEW_NOTES):
            abort(401)

        notes = app.files.db.admin_notes.find_one({"_id": identifier})
        app.security.add_audit_log("got_notes", request.user, request.ip, {"identifier": identifier})
        if notes:
            return notes, 200
        else:
            return {
                "_id": identifier,
                "notes": "",
                "last_modified_by": None,
                "last_modified_at": None
            }, 200
    elif request.method == "PUT":
        if not app.security.has_permission(request.permissions, Permissions.EDIT_NOTES):
            abort(401)
        elif "notes" not in request.json:
            return {"error": True, "type": "Syntax"}, 400
        elif not isinstance(request.json["notes"], str):
            return {"error": True, "type": "Datatype"}, 400
        else:
            notes = {
                "_id": identifier,
                "notes": request.json["notes"],
                "last_modified_by": request.user,
                "last_modified_at": int(time.time())
            }
            app.files.db.admin_notes.update_one({"_id": identifier}, {"$set": notes}, upsert=True)
            app.security.add_audit_log("updated_notes", request.user, request.ip, {"identifier": identifier, "notes": request.json["notes"]})
            return notes


@app.route('/admin/users/<username>', methods=["GET"])
def get_user_admin(username):
    if not request.permissions:
        abort(401)
    
    account = app.files.db.usersv0.find_one({"lower_username": username.lower()})
    if not account:
        abort(404)
    
    payload = {
        "_id": account["_id"],
        "created": account["created"],
        "uuid": account["uuid"],
        "pfp_data": account["pfp_data"],
        "quote": account["quote"],
        "permissions": account["permissions"],
        "last_seen": account["last_seen"]
    }

    if app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        payload.update({"settings": DEFAULT_USER_SETTINGS})
        user_settings = app.files.db.user_settings.find_one({"_id": account["_id"]})
        if user_settings:
            del user_settings["_id"]
            payload["settings"].update(user_settings)
    elif app.security.has_permission(request.permissions, Permissions.VIEW_INBOXES):
        payload.update({"settings": {"unread_inbox": DEFAULT_USER_SETTINGS}})
        user_settings = app.files.db.user_settings.find_one({"_id": account["_id"]}, projection={"unread_inbox": 1})
        if user_settings:
            del user_settings["_id"]
            payload["settings"].update(user_settings)

    if app.security.has_permission(request.permissions, Permissions.VIEW_BAN_STATES):
        payload["ban"] = account["ban"]

    if app.security.has_any_permission(request.permissions, [Permissions.VIEW_ALTS, Permissions.VIEW_IPS]):
        netlogs = list(app.files.db.netlog.find({"_id.user": username}))

        """
        if app.security.has_permission(request.permissions, Permissions.VIEW_ALTS):
            payload["alts"] = set()
            for network in networks:
                for user in network["users"]:
                    payload["alts"].add(user)
            payload["alts"] = list(payload["alts"])
        """

        if app.security.has_permission(request.permissions, Permissions.VIEW_IPS):
            payload["netlogs"] = []
            for netlog in netlogs:
                payload["netlogs"].append({
                    "ip": netlog["_id"]["ip"],
                    "last_used": netlog["last_used"]
                })
    
    # Add log
    app.security.add_audit_log("got_user", request.user, request.ip, {"username": username, "returned_fields": list(payload.keys())})

    return payload, 200


@app.route('/admin/users/<username>/inbox', methods=["GET"])
def get_user_inbox_admin(username):
    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Check authorization
    if not app.security.has_permission(request.permissions, Permissions.VIEW_INBOXES):
        abort(401)

    # Get posts
    query = {"post_origin": "inbox", "isDeleted": False, "u": username}
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Add log
    app.security.add_audit_log("got_inbox", request.user, request.ip, {"username": username})

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("posts", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@app.route("/admin/kick/<username>", methods=["POST"])
def kcik_user(username):
    app.supporter.kickUser(username)
    return "", 204


@app.errorhandler(401)  # Unauthorized
def unauthorized(e):
	return {"error": True, "type": "Unauthorized"}, 401


@app.errorhandler(404)  # We do need a 404 handler.
def page_not_found(e):
	return {"error": True, "type": "notFound"}, 404


@app.errorhandler(405)  # Method not allowed
def not_allowed(e):
	return {"error": True, "type": "methodNotAllowed"}, 405


@app.errorhandler(500)  # Internal
def internal(e):
	return {"error": True, "type": "Internal"}, 500

from flask import Flask, request
from flask_cors import CORS
from security import Security, Permissions
from supporter import Supporter
from meower import Meower
from files import Files
import time
import secrets

app = Flask(__name__, static_folder="static")
cors = CORS(app, resources=r'*', origins=r'*', max_age=86400)

# Init libraries
supporter = Supporter()
filesystem = Files(
    logger = supporter.log,
    errorhandler = supporter.full_stack
)
accounts = Security(
    files = filesystem,
    supporter = supporter,
    logger = supporter.log,
    errorhandler = supporter.full_stack
)
meower = Meower(
    supporter = supporter,
    cl = None,
    logger = supporter.log,
    errorhandler = supporter.full_stack,
    accounts = accounts,
    files = filesystem
)

def fetch_post_from_storage(post_id):
    if filesystem.does_item_exist("posts", post_id):
        result, payload = filesystem.load_item("posts", post_id)
        
        if result:
            if (payload["post_origin"] != "home") or payload["isDeleted"]:
                payload = {
                    "isDeleted": True
                }
            else:
                payload["isDeleted"] = False
        
        return True, result, payload
    else:
        return True, False, {}

@app.before_request
def pre_request_check_auth():
    request.user = None
    request.permissions = 0
    if ("username" in request.headers) and ("token" in request.headers):
        username = request.headers.get("username")
        if len(username) > 20:
            username = username[:20]
        token = request.headers.get("token")
        if len(token) > 86:
            token = token[:86]
        filecheck, fileread, accountData = accounts.get_account(username, False, False)
        if filecheck and fileread:
            if (token in accountData["tokens"]) and (not accountData["banned"]):
                request.user = accountData["_id"]
                request.permissions = accountData["permissions"]


@app.route('/', methods = ['GET']) # Index
def index():
	if request.method == "GET":
		return "Hello world! The Meower API is working, but it's under construction. Please come back later.", 200

@app.route('/ip', methods = ['GET']) # Get the Cloudflare IP address
def ip_tracer():
	return "", 410

@app.route('/favicon.ico', methods = ['GET']) # Favicon, my ass. We need no favicon for an API.
def favicon_my_ass():
	return '', 200

@app.route('/posts', methods=["GET"])
def get_post():
    post_id = request.args.get("id")
    if not post_id:
        return {"error": True, "type": "noQueryString"}, 200
    
    result, post_data = filesystem.load_item("posts", post_id)
    if (not result) or (post_data.get("isDeleted") and (not accounts.has_permission(request.permissions, Permissions.DELETE_POSTS))):
        return {"error": True, "type": "notFound"}, 404
    elif post_data.get("post_origin") != "home":
        if request.user is None:
            return {"error": True, "type": "notFound"}, 404

        fileread, filedata = filesystem.load_item("chats", post_data["post_origin"])
        if (not fileread) or (request.user not in filedata["members"]):
            return {"error": True, "type": "notFound"}, 404

    post_data["error"] = False
    return post_data, 200

@app.route('/posts/<chatid>', methods=["GET"])
def get_mychat_posts(chatid):
    page = 1
    autoget = False
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 400

    if "autoget" in args:
        autoget = True

    if request.user is None:
        return {"error": True, "type": "Unauthorized"}, 401

    fileread, filedata = filesystem.load_item("chats", chatid)
    if not fileread:
        return {"error": True, "type": "notFound"}, 404
    
    if not accounts.has_permission(request.permissions, Permissions.VIEW_CHATS):
        if filedata["deleted"] or (request.user not in filedata["members"]):
            return {"error": True, "type": "notFound"}, 404

    payload = meower.getIndex(location="posts", query={"post_origin": chatid, "isDeleted": False}, truncate=True, page=page)
    if not autoget:
        for i in range(len(payload["index"])):
            payload["index"][i] = payload["index"][i]["_id"]
        payload["error"] = False
        return payload, 200
    else:
        supporter.log("Loaded index, data {0}".format(payload))
        try:
            tmp_payload = {"error": False, "autoget": [], "page#": payload["page#"], "pages": payload["pages"]}
            tmp_payload["autoget"] = payload["index"]
            
            return tmp_payload, 200
        except:
            return {"error": True, "type": "Internal"}, 500

@app.route('/home', methods=["GET"])
def get_home():
    page = 1
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)

            if (page > 1) and (request.user is None):
                return {"error": True, "type": "Unauthorized"}, 401
            else:
                supporter.log("{0} requested to get page {1} of home".format(request.user, page))
        except:
            return {"error": True, "type": "Datatype"}, 400

    try:
        posts = meower.getIndex(location="posts", query={"post_origin": "home", "isDeleted": False}, truncate=True, page=page)
        payload = {"error": False, "autoget": [], "page#": posts["page#"], "pages": (1 if (request.user is None) else posts["pages"])}
        payload["autoget"] = posts["index"]
        
        return payload, 200
    except:
        return {"error": True, "type": "Internal"}, 500

@app.route('/reports', methods=["GET"])
def get_reports():
    page = 1
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 400

    if accounts.has_permission(request.permissions, Permissions.DELETE_POSTS) and accounts.has_any_permission(request.permissions, [Permissions.CLEAR_USER_QUOTES, Permissions.SEND_ALERTS, Permissions.EDIT_BAN_STATES]):
        query = {}
    elif accounts.has_permission(request.permissions, Permissions.DELETE_POSTS):
        query = {"type": 0}
    elif accounts.has_any_permission(request.permissions, [Permissions.CLEAR_USER_QUOTES, Permissions.SEND_ALERTS, Permissions.EDIT_BAN_STATES]):
        query = {"type": 1}
    else:
        return {"error": True, "type": "Unauthorized"}, 401

    payload = meower.getIndex(location="reports", query=query, truncate=True, sort="_id", page=page)
    supporter.log("Loaded index, data {0}".format(payload))
    try:
        tmp_payload = {"error": False, "autoget": [], "page#": payload["page#"], "pages": payload["pages"]}
        for item in payload["index"]:
            if item["type"] == 0:
                fileread, filedata = filesystem.load_item("posts", item["_id"])
                if fileread:
                    filedata["type"] = 0
                    tmp_payload["autoget"].append(filedata)
                else:
                    continue
            elif item["type"] == 1:
                filecheck, fileget, filedata = accounts.get_account(item["_id"], True, True)
                if filecheck and fileget:
                    filedata["type"] = 1
                    tmp_payload["autoget"].append(filedata)
                else:
                    continue
        
        return tmp_payload, 200
    except:
        return {"error": True, "type": "Internal"}, 500

@app.route("/notes/<identifier>", methods=["GET", "PUT"])
def admin_notes(identifier):
    if request.method == "GET":
        if not accounts.has_permission(request.permissions, Permissions.VIEW_NOTES):
            return {"error": True, "type": "Unauthorized"}, 401

        fileread, filedata = filesystem.load_item("admin_notes", identifier)
        if fileread:
            return filedata, 200
        else:
            return {
                "_id": identifier,
                "notes": "",
                "last_modified_by": None,
                "last_modified_at": None
            }, 200
    elif request.method == "PUT":
        if not accounts.has_permission(request.permissions, Permissions.EDIT_NOTES):
            return {"error": True, "type": "Unauthorized"}, 401

        if "notes" not in request.json:
            return {"error": True, "type": "Syntax"}, 400
        elif not isinstance(request.json["notes"], str):
            return {"error": True, "type": "Datatype"}, 400
        else:
            updated_notes_obj = {
                "_id": identifier,
                "notes": request.json["notes"],
                "last_modified_by": request.user,
                "last_modified_at": int(time.time())
            }
            filewrite = filesystem.update_item("admin_notes", identifier, updated_notes_obj, upsert=True)
            if filewrite:
                return updated_notes_obj, 200
            else:
                return {"error": True, "type": "Internal"}, 500

@app.route('/inbox', methods=["GET"])
def get_inbox():
    page = 1
    autoget = False
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 400

    if "autoget" in args:
        autoget = True

    if request.user is None:
        return {"error": True, "type": "Unauthorized"}, 401
    
    if ("user" in args) and accounts.has_permission(request.permissions, Permissions.VIEW_INBOXES):
        user = args["user"]
    else:
        user = request.user

    payload = meower.getIndex(location="posts", query={"post_origin": "inbox", "isDeleted": False, "u": {"$in": [user, "Server"]}}, truncate=True, page=page)
    if not autoget:
        for i in range(len(payload["index"])):
            payload["index"][i] = payload["index"][i]["_id"]
        payload["error"] = False
        return payload, 200
    else:
        supporter.log("Loaded index, data {0}".format(payload))
        try:
            tmp_payload = {"error": False, "autoget": [], "page#": payload["page#"], "pages": payload["pages"]}
            tmp_payload["autoget"] = payload["index"]
            
            return tmp_payload, 200
        except:
            return {"error": True, "type": "Internal"}, 500

@app.route('/chats', methods=["GET"])
def get_chats():
    page = 1
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 400

    if request.user is None:
        return {"error": True, "type": "Unauthorized"}, 401
    
    if ("user" in args) and (accounts.has_permission(request.permissions, Permissions.VIEW_CHATS)):
        user = args["user"]
    else:
        user = request.user

    query = {"members": {"$all": [user]}, "deleted": False}
    if ("include_deleted" in args) and (accounts.has_permission(request.permissions, Permissions.VIEW_CHATS)):
        del query["deleted"]

    chat_index = meower.getIndex(location="chats", query=query, truncate=True, page=page, sort="last_active")
    return {
        "error": False,
        "all_chats": chat_index["index"],
        "index": [chat["_id"] for chat in chat_index["index"]],
        "page#": chat_index["page#"],
        "pages": chat_index["pages"],
        "query": chat_index["query"]
    }, 200

@app.route('/chats/<chatid>', methods=["GET"])
def get_chat(chatid):
    if request.user is None:
        return {"error": True, "type": "Unauthorized"}, 401
    
    fileread, chatdata = filesystem.load_item("chats", chatid)
    if not fileread:
        return {"error": True, "type": "notFound"}, 404

    if not accounts.has_permission(request.permissions, Permissions.VIEW_CHATS):
        if chatdata["deleted"] or (request.user not in chatdata["members"]):
            return {"error": True, "type": "notFound"}, 404
    
    chatdata["error"] = False
    return chatdata, 200

@app.route('/search/home', methods=["GET"])
def search_home():
    page = 1
    autoget = False
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 400

    if "autoget" in args:
        autoget = True

    if "q" in args:
        query = args.get("q")
    else:
        return {"error": True, "type": "Syntax"}, 400

    if len(query) > 360:
        query = query[:360]

    payload = meower.getIndex(location="posts", query={"post_origin": "home", "isDeleted": False, "$text": {"$search": query}}, truncate=True, page=page)
    if not autoget:
        for i in range(len(payload["index"])):
            payload["index"][i] = payload["index"][i]["_id"]
        payload["error"] = False
        return payload, 200
    else:
        supporter.log("Loaded index, data {0}".format(payload))
        try:
            tmp_payload = {"error": False, "autoget": [], "page#": payload["page#"], "pages": payload["pages"]}
            tmp_payload["autoget"] = payload["index"]
            
            return tmp_payload, 200
        except:
            return {"error": True, "type": "Internal"}, 500

@app.route('/search/users', methods=["GET"])
def search_users():
    page = 1
    autoget = False
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 400

    if "autoget" in args:
        autoget = True

    if "q" in args:
        query = args.get("q")
    else:
        return {"error": True, "type": "Syntax"}, 400

    if len(query) > 20:
        query = query[:20]

    payload = meower.getIndex(location="usersv0", query={"lower_username": {"$regex": query.lower()}}, truncate=True, page=page, sort="created")
    if not autoget:
        for i in range(len(payload["index"])):
            payload["index"][i] = payload["index"][i]["_id"]
        payload["error"] = False
        return payload, 200
    else:
        supporter.log("Loaded index, data {0}".format(payload))
        try:
            tmp_payload = {"error": False, "autoget": [], "page#": payload["page#"], "pages": payload["pages"]}
            for user in payload["index"]:
                filecheck, fileget, filedata = accounts.get_account(user["_id"], True, True)
                if filecheck and fileget:
                    tmp_payload["autoget"].append(filedata)
                else:
                    continue
            
            return tmp_payload, 200
        except:
            return {"error": True, "type": "Internal"}, 500

@app.route('/users/<username>', methods=["GET", "PATCH"])
def get_user(username):
    filecheck, fileget, filedata = accounts.get_account(username, (request.user != username), True)
    if not (filecheck and fileget):
        return {"error": True, "type": "notFound"}, 404
    
    if request.method == "GET":
        filedata["error"] = False
        return filedata, 200
    elif request.method == "PATCH":
        if "permissions" in request.json:
            if not accounts.has_permission(request.permissions, Permissions.SYSADMIN):
                return {"error": True, "type": "Unauthorized"}, 401
            elif not isinstance(request.json["permissions"], int):
                return {"error": True, "type": "Datatype"}, 400
            elif accounts.has_permission(filedata["permissions"], Permissions.SYSADMIN):
                return {"error": True, "type": "Unauthorized"}, 401
            elif accounts.has_permission(request.json["permissions"], Permissions.SYSADMIN):
                return {"error": True, "type": "Unauthorized"}, 401
            
            accounts.update_setting(username, {"permissions": request.json["permissions"]}, forceUpdate=True)

            return "", 204
        else:
            return {"error": True, "type": "Syntax"}, 400

@app.route('/users/<username>/admin', methods=["GET"])
def get_user_admin(username):
    if not request.permissions:
        return {"error": True, "type": "Unauthorized"}, 401
    
    filecheck, fileget, filedata = accounts.get_account(username, False, False)
    if not (filecheck and fileget):
        return {"error": True, "type": "notFound"}, 404
    
    payload = {
        "_id": filedata["_id"],
        "created": filedata["created"],
        "uuid": filedata["uuid"],
        "pfp_data": filedata["pfp_data"],
        "quote": filedata["quote"],
        "permissions": filedata["permissions"],
        "last_seen": filedata["last_seen"]
    }

    if accounts.has_permission(request.permissions, Permissions.VIEW_INBOXES):
        payload["unread_inbox"] = filedata["unread_inbox"]

    if accounts.has_permission(request.permissions, Permissions.VIEW_BAN_STATES):
        payload["ban"] = filedata["ban"]

    if accounts.has_permission(request.permissions, Permissions.VIEW_IPS):
        payload["last_ip"] = filedata["last_ip"]

    if accounts.has_any_permission(request.permissions, [Permissions.VIEW_ALTS, Permissions.VIEW_IPS]):
        networks = list(filesystem.db.netlog.find({"users": {"$all": [username]}}))

        if accounts.has_permission(request.permissions, Permissions.VIEW_ALTS):
            payload["alts"] = set()
            for network in networks:
                for user in network["users"]:
                    payload["alts"].add(user)
            payload["alts"] = list(payload["alts"])

        if accounts.has_permission(request.permissions, Permissions.VIEW_IPS):
            payload["ips"] = [network["_id"] for network in networks]
    
    return payload

@app.route('/users/<username>/admin/quote', methods=["DELETE"])
def clear_user_quote(username):
    if not accounts.has_permission(request.permissions, Permissions.CLEAR_USER_QUOTES):
        return {"error": True, "type": "Unauthorized"}, 401

    filecheck, fileread, filewrite = accounts.update_setting(username, {"quote": ""}, forceUpdate=True)
    if not (filecheck and fileread):
        return {"error": True, "type": "notFound"}, 404
    elif not filewrite:
        return {"error": True, "type": "Internal"}, 500
    else:
        return "", 204

@app.route('/users/<username>/admin/impersonate', methods=["GET"])
def impersonate_user(username):
    if not accounts.has_permission(request.permissions, Permissions.IMPERSONATE_USERS):
        return {"error": True, "type": "Unauthorized"}, 401

    filecheck, fileget, filedata = accounts.get_account(username, False, False)
    if filecheck and fileget:
        token = secrets.token_urlsafe(64)

        filedata["tokens"].append(token)
        accounts.update_setting(username, {"tokens": filedata["tokens"]}, forceUpdate=True)

        payload = {
            "username": username,
            "token": token
        }
        return payload, 200
    else:
        return {"error": True, "type": "notFound"}, 404

@app.route('/users/<username>/posts', methods=["GET"])
def get_user_posts(username):
    page = 1
    autoget = False
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 400
    
    if "autoget" in args:
        autoget = True

    payload = meower.getIndex(location="posts", query={"u": username, "post_origin": "home", "isDeleted": False}, truncate=True, page=page, index_hint="user_search")
    if not autoget:
        for i in range(len(payload["index"])):
            payload["index"][i] = payload["index"][i]["_id"]
        payload["error"] = False
        return payload, 200
    else:
        supporter.log("Loaded index, data {0}".format(payload))
        try:
            tmp_payload = {"error": False, "autoget": [], "page#": payload["page#"], "pages": payload["pages"]}
            tmp_payload["autoget"] = payload["index"]
            
            return tmp_payload, 200
        except:
            return {"error": True, "type": "Internal"}, 500

@app.route('/statistics', methods=["GET"])
def get_statistics():
    try:
        users = filesystem.count_items("usersv0", {})
        posts = filesystem.count_items("posts", {"isDeleted": False})
        chats = filesystem.count_items("chats", {})
        return {"error": False, "users": users, "posts": posts, "chats": chats}, 200
    except:
        return {"error": True, "type": "Internal"}, 500

@app.route('/status', methods=["GET"])
def get_status():
    result, payload = filesystem.load_item("config", "status")
    if result:
        return {"isRepairMode": payload["repair_mode"], "scratchDeprecated": payload["is_deprecated"]}, 200
    else:
        return {"error": True, "type": "Internal"}, 500

@app.errorhandler(405) # Method not allowed
def not_allowed(e):
	return {"error": True, "type": "methodNotAllowed"}, 405

@app.errorhandler(500) # Internal
def internal(e):
	return {"error": True, "type": "Internal"}, 500

@app.errorhandler(404) # We do need a 404 handler.
def page_not_found(e):
	return {"error": True, "type": "notFound"}, 404

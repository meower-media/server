from flask import Flask, request
from flask_cors import CORS
from security import Security
from supporter import Supporter
from meower import Meower
from files import Files

app = Flask(__name__, static_folder="static")
cors = CORS(app, resources=r'*')

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
    request.lvl = 0
    if ("username" in request.headers) and ("token" in request.headers):
        username = request.headers.get("username")
        if len(username) > 20:
            username = username[:20]
        token = request.headers.get("token")
        if len(token) > 64:
            username = username[:64]
        filecheck, fileread, filedata = accounts.get_account(username, False, False)
        if filecheck and fileread:
            if (token in filedata["tokens"]) and (filedata["banned"] == False):
                request.user = filedata["_id"]
                request.lvl = filedata["lvl"]

@app.route('/', methods = ['GET']) # Index
def index():
	if request.method == "GET":
		return "Hello world! The Meower API is working, but it's under construction. Please come back later.", 200

@app.route('/ip', methods = ['GET']) # Get the Cloudflare IP address
def ip_tracer():
	if request.method == "GET":
		if "Cf-Connecting-Ip" in request.headers:
			return str(request.headers["Cf-Connecting-Ip"]), 200
		else:
			return str(request.remote_addr)
	else:
		return {"error": True, "type": "notAllowed"}, 405

@app.route('/favicon.ico', methods = ['GET']) # Favicon, my ass. We need no favicon for an API.
def favicon_my_ass():
	return '', 200

@app.route('/posts', methods=["GET"])
def get_post():
    post_id = ""
    args = request.args
    if "id" in args:
        post_id = args.get("id")
        filecheck, fileget, filedata = fetch_post_from_storage(post_id)
        if filecheck and fileget:
            filedata["error"] = False
            return filedata, 200
        else:
            if filecheck and (not fileget):
                return {"error": True, "type": "notFound"}, 404
            else:
                return {"error": True, "type": "Internal"}, 500
    else:
        return {"error": True, "type": "noQueryString"}, 200

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
            return {"error": True, "type": "Datatype"}, 500

    if "autoget" in args:
        autoget = True

    if request.user is None:
        return {"error": True, "type": "Unauthorized"}, 401

    fileread, filedata = filesystem.load_item("chats", chatid)
    if fileread:
        if request.user not in filedata["members"]:
            return {"error": True, "type": "Forbidden"}, 403
    else:
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
    autoget = False
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 500
    
    if "autoget" in args:
        autoget = True

    payload = meower.getIndex(location="posts", query={"post_origin": "home", "isDeleted": False}, truncate=True, page=page)
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

@app.route('/reports', methods=["GET"])
def get_reports():
    page = 1
    args = request.args
    
    if "page" in args:
        page = args.get("page")
        try:
            page = int(page)
        except:
            return {"error": True, "type": "Datatype"}, 500

    if (request.user == None) or (request.lvl < 1):
        return {"error": True, "type": "Unauthorized"}, 401

    payload = meower.getIndex(location="reports", query={}, truncate=True, page=page)
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
            return {"error": True, "type": "Datatype"}, 500

    if "autoget" in args:
        autoget = True

    if request.user is None:
        return {"error": True, "type": "Unauthorized"}, 401

    payload = meower.getIndex(location="posts", query={"post_origin": "inbox", "u": {"$in": [request.user, "Server"]}, "isDeleted": False}, truncate=True, page=page)
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
            return {"error": True, "type": "Datatype"}, 500

    if "autoget" in args:
        autoget = True

    if "q" in args:
        query = args.get("q")
    else:
        return {"error": True, "type": "Syntax"}, 400

    if len(query) > 360:
        query = query[:360]

    payload = meower.getIndex(location="posts", query={"post_origin": "home", "p": {"$regex": query}, "isDeleted": False}, truncate=True, page=page)
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

    payload = meower.getIndex(location="usersv0", query={"lower_username": {"$regex": query.lower()}}, truncate=True, page=page, sort="lower_username")
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

@app.route('/users/<username>', methods=["GET"])
def get_user(username):
    filecheck, fileget, filedata = accounts.get_account(username, True, True)
    if filecheck and fileget:
        filedata["error"] = False
        return filedata, 200
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
            return {"error": True, "type": "Datatype"}, 500
    
    if "autoget" in args:
        autoget = True

    payload = meower.getIndex(location="posts", query={"post_origin": "home", "u": username, "isDeleted": False}, truncate=True, page=page)
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

@app.route("/statistics", methods=["GET"])
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
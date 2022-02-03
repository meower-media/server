from flask import Flask, request
from flask_cors import CORS
from security import Security
from supporter import Supporter
from meower import Meower
from files import Files
import json

app = Flask(__name__)
cors = CORS(app, resources=r'*')

repair_mode = False

# Init libraries
supporter = Supporter()
filesystem = Files(
    logger = supporter.log,
    errorhandler = supporter.full_stack
)
accounts = Security(
    files = filesystem,
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
    status, payload = filesystem.get_directory("/Storage/Categories/Home/Messages/")
    if status:
        if post_id in payload:
            result, payload = filesystem.load_file("/Storage/Categories/Home/Messages/{0}".format(post_id))
            
            if result:
                if ("isDeleted" in payload) and (payload["isDeleted"]):
                    payload = {
                        "isDeleted": True
                    }
                    
                else:
                    payload["isDeleted"] = False
            
            return True, result, payload
        else:
            return True, False, {}
    else:
        return False, False, {}

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
			return {"error": True, "type": "Internal"}, 500
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
    
    result, payload = meower.getIndex(location="/Storage/Categories/Home/Indexes/", mode=3, query=supporter.timestamp(5), noCheck=True, convert=False, page=page)
    if result != 0:
        if not autoget:
            payload["error"] = False
            return payload, 200
        else:
            try:
                tmp_payload = {"error": False, "autoget": []}
                
                for post_id in payload["index"]:
                    filecheck, fileget, filedata = fetch_post_from_storage(post_id)
                    if filecheck and fileget:
                        tmp_payload["autoget"].append(filedata)
                    else:
                        if filecheck and (not fileget):
                            tmp_payload["autoget"].append({"error": True, "type": "notFound"})
                        else:
                            tmp_payload["autoget"].append({"error": True, "type": "Internal"})
                
                return tmp_payload, 200
            except Exception as e:
                print(e)
                return {"error": True, "type": "Internal"}, 500
    else:
        return {"error": True, "type": "Internal"}, 500

@app.route('/status', methods=["GET"])
def get_status():
    return {"isRepairMode": repair_mode}, 200

@app.errorhandler(405) # Method not allowed
def not_allowed(e):
	return {"error": True, "type": "methodNotAllowed"}, 405

@app.errorhandler(500) # Internal
def internal(e):
	return {"error": True, "type": "Internal"}, 500

@app.errorhandler(404) # We do need a 404 handler.
def page_not_found(e):
	return {"error": True, "type": "notFound"}, 404

if __name__ == '__main__': # Run server
	app.run(host="0.0.0.0", port=3001, debug=True)
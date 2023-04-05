from flask import Flask, request
from flask_cors import CORS

from src.common.entities import users, posts, chats, reports, audit_log
from src.common.util import errors
from src.common.database import db, redis


app = Flask(__name__, static_folder="static")
cors = CORS(app, resources=r'*')


@app.before_request
def pre_request_check_auth():
	request.user = None
	try:
		if ("username" in request.headers) and ("token" in request.headers):
			user = users.get_user(request.headers["username"])
			if (not user.banned) and (user.validate_token(request.headers["token"])):
				request.user = user
	except:
		pass


@app.route("/")
def index():
	return "Hello world! The Meower API is working, but it's under construction. Please come back later."


@app.route("/ip")  # deprecated
def ip_tracer():
	return "", 410


@app.route("/favicon.ico") # Favicon, my ass. We need no favicon for an API.
def favicon_my_ass():
	return "", 204


@app.route("/posts")
def get_post():
	# Check whether the post ID was specified
	if "id" not in request.args:
		return {"error": True, "type": "noQueryString"}, 400
	
	# Get post
	try:
		post = posts.get_post(request.args["id"])
	except errors.NotFound:
		return {"error": True, "type": "notFound"}, 404

	# Check whether the user has access to the post
	if not post.has_access(request.user):
		return {"error": True, "type": "notFound"}, 404
	
	# Return post
	return post.public


@app.route("/posts/<chat_id>")
def get_chat_posts(chat_id):
	# Get page
	try:
		page = int(request.args.get("page", 1))
	except ValueError:
		return {"error": True, "type": "Datatype"}, 400

	# Check whether the user is authenticated
	if not request.user:
		return {"error": True, "type": "Unauthorized"}, 401

	# Get chat
	try:
		chat = chats.get_chat(chat_id)
	except errors.NotFound:
		return {"error": True, "type": "notFound"}, 404

	# Check whether the user is in the chat
	if request.user.username not in chat.members:
		return {"error": True, "type": "notFound"}, 404
	
	# Get posts
	pages, fetched_posts = posts.get_posts(chat_id, page=page)

	# Return posts
	return {
		"error": False,
		"autoget": [post.public for post in fetched_posts],
		"page#": page,
		"pages": pages
	}


@app.route("/home")
def get_home():
	# Get page
	try:
		page = int(request.args.get("page", 1))
	except ValueError:
		return {"error": True, "type": "Datatype"}, 400

	# Check whether the user is authenticated
	if (not request.user) and (page > 1):
		return {"error": True, "type": "Unauthorized"}, 401
	
	# Get posts
	pages, fetched_posts = posts.get_posts("home", page=page)

	# Return posts
	return {
		"error": False,
		"autoget": [post.public for post in fetched_posts],
		"page#": page,
		"pages": pages
	}


@app.route("/reports")
def get_reports():
	# Get page
	try:
		page = int(request.args.get("page", 1))
	except ValueError:
		return {"error": True, "type": "Datatype"}, 400

	# Check whether the user is authenticated
	if (not request.user) or (request.user.lvl < 1):
		return {"error": True, "type": "Unauthorized"}, 401
	
	# Get reports
	pages, fetched_reports = reports.get_reports(page=page)

	# Return reports
	return {
		"error": False,
		"autoget": [report.admin for report in fetched_reports],
		"page#": page,
		"pages": pages
	}


@app.route("/logs")
def get_logs():
	# Get page
	try:
		page = int(request.args.get("page", 1))
	except ValueError:
		return {"error": True, "type": "Datatype"}, 400

	# Check whether the user is authenticated
	if (not request.user) or (request.user.lvl < 2):
		return {"error": True, "type": "Unauthorized"}, 401
	
	# Get logs
	pages, fetched_logs = audit_log.get_logs(page=page)

	# Return logs
	return {
		"error": False,
		"autoget": [log.admin for log in fetched_logs],
		"page#": page,
		"pages": pages
	}


@app.route("/search/home")
def search_home():
	# Check whether the query was specified
	if "q" not in request.args:
		return {"error": True, "type": "noQueryString"}, 400

	# Get page
	try:
		page = int(request.args.get("page", 1))
	except ValueError:
		return {"error": True, "type": "Datatype"}, 400
	
	# Get posts
	pages, fetched_posts = posts.search_posts("home", request.args["q"], page=page)

	# Return posts
	return {
		"error": False,
		"autoget": [post.public for post in fetched_posts],
		"page#": page,
		"pages": pages
	}


@app.route("/search/users")
def search_users():
	# Check whether the query was specified
	if "q" not in request.args:
		return {"error": True, "type": "noQueryString"}, 400

	# Get page
	try:
		page = int(request.args.get("page", 1))
	except ValueError:
		return {"error": True, "type": "Datatype"}, 400
	
	# Get users
	pages, fetched_users = users.search_users(request.args["q"], page=page)

	# Return users
	return {
		"error": False,
		"autoget": [user.public for user in fetched_users],
		"page#": page,
		"pages": pages
	}


@app.route("/inbox")
def get_inbox():
	# Get page
	try:
		page = int(request.args.get("page", 1))
	except ValueError:
		return {"error": True, "type": "Datatype"}, 400

	# Check whether the user is authenticated
	if not request.user:
		return {"error": True, "type": "Unauthorized"}, 401
	
	# Get posts
	pages, fetched_posts = posts.get_inbox_messages(request.user.username, page=page)

	# Return posts
	return {
		"error": False,
		"autoget": [post.public for post in fetched_posts],
		"page#": page,
		"pages": pages
	}


@app.route("/users/<username>")
def get_user(username):
	# Get user
	try:
		user = users.get_user(username)
	except errors.NotFound:
		return {"error": True, "type": "notFound"}, 404
	
	# Return user
	return user.public


@app.route("/users/<username>/posts")
def get_user_posts(username):
	# Get page
	try:
		page = int(request.args.get("page", 1))
	except ValueError:
		return {"error": True, "type": "Datatype"}, 400
	
	# Check if user exists
	if not users.username_exists(username):
		return {"error": True, "type": "notFound"}, 404

	# Get posts
	pages, fetched_posts = posts.get_posts("home", author=username, page=page)

	# Return posts
	return {
		"error": False,
		"autoget": [post.public for post in fetched_posts],
		"page#": page,
		"pages": pages
	}


@app.route("/statistics")
def get_statistics():
	return {
		"error": False,
		"users": db.users.estimated_document_count(),
		"posts": db.posts.estimated_document_count(),
		"chats": db.chats.estimated_document_count()
	}


@app.route("/status")
def get_status():
	return {
		"error": False,
		"isRepairMode": (redis.exists("repair_mode") == 1),
		"scratchDeprecated": False
	}


@app.errorhandler(404) # We do need a 404 handler.
def page_not_found(e):
	return {"error": True, "type": "notFound"}, 404


@app.errorhandler(405) # Method not allowed
def not_allowed(e):
	return {"error": True, "type": "methodNotAllowed"}, 405


@app.errorhandler(500) # Internal
def internal(e):
	return {"error": True, "type": "Internal"}, 500

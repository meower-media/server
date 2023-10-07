from flask import Blueprint, current_app as app, request, abort
import pymongo


search_bp = Blueprint("search_bp", __name__, url_prefix="/search")


@search_bp.get("/home")
def search_home():
    # Get query
    q = request.args.get("q")
    if not q:
        abort(400)
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


@search_bp.get("/users")
def search_users():
    # Get query
    q = request.args.get("q")
    if not q:
        abort(400)
    elif len(q) > 20:
        q = q[:20]

    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Get users
    query = {"lower_username": {"$regex": q.lower()}}
    usernames = [user["_id"] for user in app.files.db.usersv0.find(query, skip=(page-1)*25, limit=25, projection={"_id": 1})]

    # Return users
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

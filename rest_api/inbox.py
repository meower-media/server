from quart import Blueprint, current_app as app, request, abort
import pymongo


inbox_bp = Blueprint("inbox_bp", __name__, url_prefix="/inbox")


@inbox_bp.get("/")
async def get_inbox_posts():
    # Check authorization
    if not request.user:
        abort(401)

    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Get posts
    query = {"post_origin": "inbox", "isDeleted": False, "$or": [{"u": request.user}, {"u": "Server"}]}
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

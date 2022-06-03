from flask import Blueprint, request, abort
from flask import current_app as app

search = Blueprint("search_blueprint", __name__)

@search.route("/profiles", methods=["GET"])
def search_profiles():
    if not ("q" in request.args):
        return app.respond({"type": "missingField"}, 400, error=True)

    # Extract query and page for simplicity
    query = str(request.args.get("q"))
    if "page" in request.args:
        page = int(request.args.get("page"))
    else:
        page = 1

    # Get index
    index = app.meower.files.find_items("usersv0", {"lower_username": {"$regex": query.lower()}, "flags.isDeleted": False}, sort="lower_username", truncate=True, page=page)

    # Reverse index so it's in order
    index["index"].reverse()

    # Return payload
    return app.respond(index, 200, error=False)

@search.route("/posts", methods=["GET"])
def search_home_posts():
    if not ("q" in request.args):
        return app.respond({"type": "missingField"}, 400, error=True)
    
    # Extract query and page for simplicity
    query = str(request.args.get("q"))
    if "page" in request.args:
        page = int(request.args.get("page"))
    else:
        page = 1
    autoget = ("autoget" in request.args)

    # Get index
    index = app.meower.files.find_items("posts", {"post_origin": "home", "p": {"$regex": query}, "isDeleted": False}, sort="t.e", truncate=True)

    # Auto get
    if autoget:
        index["autoget"] = []
        for post_id in index["index"]:
            file_read, post = app.meower.files.load_item("posts", post_id)
            if file_read:
                index["autoget"].append(post)
    
    # Return payload
    return app.respond(index, 200, error=False)
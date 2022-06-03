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
    del index["items"]

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

    # Get index
    query_get = app.meower.files.find_items("posts", {"post_origin": "home", "p": {"$regex": query}, "isDeleted": False}, sort="t.e", truncate=True, page=page)

    # Auto get
    if not ("autoget" in request.args):
        del query_get["items"]
    
    # Return payload
    return app.respond(query_get, 200, error=False)

@search.route("/chats", methods=["GET"])
def search_public_chats():
    if not ("q" in request.args):
        return app.respond({"type": "missingField"}, 400, error=True)
    
    # Extract query and page for simplicity
    query = str(request.args.get("q"))
    if "page" in request.args:
        page = int(request.args.get("page"))
    else:
        page = 1

    # Get index
    query_get = app.meower.files.find_items("chats", {"nickname": {"$regex": query}, "isPublic": True, "isDeleted": False}, sort="nickname", truncate=True, page=page)
    
    # Auto get
    if not ("autoget" in request.args):
        del query_get["items"]

    # Return payload
    return app.respond(query_get, 200, error=False)
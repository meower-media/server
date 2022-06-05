from flask import Blueprint, request, abort
from flask import current_app as app

users = Blueprint("users_blueprint", __name__)

@users.route("/<user>", methods=["GET"])
def get_profile(user):
    # Get user data
    file_read, userdata = app.meower.accounts.get_account(user)
    if not file_read:
        abort(404)

    return app.respond(userdata["profile"], 200, error=False)

@users.route("/<user>/posts", methods=["GET"])
def search_user_posts(user):
    # Extract page for simplicity
    if "page" in request.args:
        page = int(request.args.get("page"))
    else:
        page = 1

    # Get index
    query_get = app.meower.files.find_items("posts", {"post_origin": "home", "u": user, "isDeleted": False}, sort="t.e", truncate=True, page=page)

    # Auto get
    if not ("autoget" in request.args):
        del query_get["items"]
    
    # Return payload
    return app.respond(query_get, 200, error=False)
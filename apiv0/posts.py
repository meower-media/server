from flask import Blueprint, request
from flask import current_app as app

posts = Blueprint("posts_blueprint", __name__)

@posts.route("/home", methods=["GET"])
def get_home():
    # Get index
    query_get = app.meower.files.find_items("posts", {"post_origin": "home", "isDeleted": False}, sort="t.e", truncate=True)
    index = query_get["index"]

    # Auto get
    if "autoget" in request.args.keys():
        query_get["autoget"] = []
        for post_id in index:
            FileRead, HasPermission, post = app.meower.posts.get_post(post_id)
            if FileRead and HasPermission:
                query_get["autoget"].append(post)

    # Return payload
    return app.respond(query_get, 200)
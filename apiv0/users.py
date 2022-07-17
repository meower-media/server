from flask import Blueprint, request
from flask import current_app as meower
import pymongo

users = Blueprint("users_blueprint", __name__)

@users.route("/<username>", methods=["GET"])
def get_profile(username):
    # Get user data
    user = meower.User(meower, username=username)
    if user.raw is None:
        return meower.respond({"type": "notFound", "message": "Requested user was not found"}, 404, error=True)

    # Return profile
    return meower.respond(user.profile, 200, error=False)

@users.route("/<username>/posts", methods=["GET"])
def search_user_posts(username):
    # Get user data
    userdata = meower.db["usersv0"].find_one({"lower_username": username})
    if userdata is None:
        return meower.respond({"type": "notFound", "message": "Requested user was not found"}, 404, error=True)

    # Get page
    if not ("page" in request.args):
        page = 1
    else:
        page = int(request.args["page"])

    # Get index
    query_get = meower.db["posts"].find({"post_origin": "home", "u": userdata["_id"], "isDeleted": False}).skip((page-1)*25).limit(25).sort("t", pymongo.DESCENDING)
    pages_amount = (meower.db["posts"].count_documents({"post_origin": "home", "u": userdata["_id"], "isDeleted": False}) // 25) + 1

    # Convert query get
    payload_posts = []
    for post in query_get:
        user = meower.User(meower, user_id=post["u"])
        if user.raw is None:
            continue
        else:
            post["u"] = user.profile
        payload_posts.append(post)

    # Create payload
    payload = {
        "posts": list(payload_posts),
        "page#": int(page),
        "pages": int(pages_amount)
    }

    # Return payload
    return meower.respond(payload, 200, error=False)
from flask import Blueprint, request, abort
from flask import current_app as meower
import pymongo

users = Blueprint("users_blueprint", __name__)

@users.route("/<user>", methods=["GET"])
def get_profile(user):
    # Get user data
    userdata = meower.db["usersv0"].find_one({"lower_username": user.lower()})
    if userdata is None:
        abort(404)
    else:
        if userdata["_id"] != request.session.user:
            del userdata["config"]
            del userdata["ratelimits"]
        else:
            userdata["config/mfa"] = (userdata["security"]["mfa_secret"] != None)
        del userdata["security"]
        userdata["profile"]["status"] = meower.user_status(userdata["_id"])

    return meower.respond(userdata, 200, error=False)

@users.route("/<user>/posts", methods=["GET"])
def search_user_posts(user):
    # Get user data
    userdata = meower.db["usersv0"].find_one({"lower_username": user.lower()})
    if userdata is None:
        abort(404)

    # Get page
    if not ("pages" in request.args):
        page = 1
    else:
        page = int(request.args.get("pages"))

    # Get index
    query_get = meower.db["posts"].find({"origin": "home", "user": userdata["_id"], "deleted": False}).skip((page-1)*25).limit(25).sort("created", pymongo.ASCENDING)
    pages_amount = (meower.db["posts"].count_documents({"origin": "home", "deleted": False}) // 25) + 1

    # Convert query get
    payload_posts = []
    for post in query_get:
        userdata = meower.db["usersv0"].find_one({"_id": post["user"]})
        if userdata is None:
            post["user"] = "Deleted"
        else:
            post["user"] = userdata["username"]
        payload_posts.append(post)
    payload_posts.reverse()

    # Create payload
    payload = {
        "posts": list(payload_posts),
        "page#": int(page),
        "pages": int(pages_amount)
    }

    # Return payload
    return meower.respond(payload, 200, error=False)
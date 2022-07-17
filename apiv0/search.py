from flask import Blueprint, request
from flask import current_app as meower
import pymongo

search = Blueprint("search_blueprint", __name__)

@search.route("/profiles", methods=["GET"])
def search_profiles():
    # Check for required params
    meower.check_for_params(["q"])

    # Get query
    query = request.args["q"]

    # Get page
    if not ("page" in request.args):
        page = 1
    else:
        page = int(request.args["page"])

    # Get index
    query_get = meower.db["usersv0"].find({"lower_username": {"$regex": query.lower()}}).skip((page-1)*25).limit(25).sort("t", pymongo.DESCENDING)
    pages_amount = (meower.db["usersv0"].count_documents({"lower_username": {"$regex": query.lower()}}) // 25) + 1

    # Convert query get
    payload_users = []
    for user in query_get:
        user = meower.User(meower, user_id=user["_id"])
        if user.raw is not None:
            payload_users.append(user)

    # Create payload
    payload = {
        "posts": list(payload_users),
        "page#": int(page),
        "pages": int(pages_amount)
    }

    # Return payload
    return meower.respond(payload, 200, error=False)

@search.route("/posts", methods=["GET"])
def search_home_posts():
    # Check for required params
    meower.check_for_params(["q"])

    # Get query
    query = request.args["q"]

    # Get page
    if not ("page" in request.args):
        page = 1
    else:
        page = int(request.args["page"])

    # Get index
    query_get = meower.db["posts"].find({"post_origin": "home", "p": {"$regex": query}, "isDeleted": False}).skip((page-1)*25).limit(25).sort("t", pymongo.DESCENDING)
    pages_amount = (meower.db["posts"].count_documents({"post_origin": "home", "p": {"$regex": query}, "isDeleted": False}) // 25) + 1

    # Convert query get
    payload_posts = []
    for post in query_get:
        user = meower.User(meower, user_id=post["u"])
        if user.raw is None:
            continue
        else:
            post["u"] = user.profile

    # Create payload
    payload = {
        "posts": list(payload_posts),
        "page#": int(page),
        "pages": int(pages_amount)
    }

    # Return payload
    return meower.respond(payload, 200, error=False)

@search.route("/chats", methods=["GET"])
def search_public_chats():
    # Check for required params
    meower.check_for_params(["q"])

    # Get query
    query = request.args["q"]

    # Get page
    if not ("page" in request.args):
        page = 1
    else:
        page = int(request.args["page"])

    # Get index
    query_get = meower.db["chats"].find({"nickname": {"$regex": query.lower()}, "public": True, "deleted": False}).skip((page-1)*25).limit(25).sort("t", pymongo.DESCENDING)
    pages_amount = (meower.db["chats"].count_documents({"nickname": {"$regex": query.lower()}, "public": True, "deleted": False}) // 25) + 1

    # Convert query get
    payload_chat = []
    for chat in query_get:
        for user_id in chat["members"]:
            user = meower.User(meower, user_id=user_id)
            chat["members"].remove(user_id)
            if user.raw is not None:
                chat["members"].append(user.profile)
        payload_chat.append(chat)

    # Create payload
    payload = {
        "posts": list(query_get),
        "page#": int(page),
        "pages": int(pages_amount)
    }

    # Return payload
    return meower.respond(payload, 200, error=False)
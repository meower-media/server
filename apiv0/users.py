from flask import Blueprint, request
from flask import current_app as meower
import pymongo
import time

users = Blueprint("users_blueprint", __name__)

@users.route("/<username>", methods=["GET"])
def get_profile(username):
    # Get user data
    user = meower.User(meower, username=username)
    if user.raw is None:
        return meower.resp(404)

    # Return profile
    return meower.resp(200, user.profile)

@users.route("/<username>/posts", methods=["GET"])
def search_user_posts(username):
    # Get user data
    userdata = meower.db.users.find_one({"lower_username": username.lower()})
    if userdata is None:
        return meower.resp(404)

    # Get page
    if not ("page" in request.args):
        page = 1
    else:
        page = int(request.args["page"])

    # Get index
    query_get = meower.db.posts.find({"post_origin": "home", "u": userdata["_id"], "isDeleted": False}).skip((page-1)*25).limit(25).sort("t", pymongo.DESCENDING)
    pages_amount = (meower.db.posts.count_documents({"post_origin": "home", "u": userdata["_id"], "isDeleted": False}) // 25) + 1

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
    return meower.resp(200, payload)

@users.route("/<username>/report", methods=["POST"])
def report_user(username):
    # Check for required data
    meower.check_for_json([{"id": "comment", "t": str, "l_min": 1, "l_max": 360}])

    # Get user data
    userdata = meower.db.users.find_one({"lower_username": username.lower()})
    if userdata is None:
        return meower.resp(404)

    # Add report
    report_status = meower.db.reports.find_one({"_id": userdata["_id"]})
    if report_status is None:
        report_status = {
            "_id": userdata["_id"],
            "type": 0,
            "users": [],
            "ips": [],
            "comments": [],
            "t": int(time.time()),
            "review_status": 0
        }
        report_status["users"].append(request.user._id)
        report_status["comments"].append({"u": request.user._id, "t": int(time.time()), "p": request.json["comment"]})
        report_status["ips"].append(request.remote_addr)
        meower.db.reports.insert_one(report_status)
    elif request.user._id not in report_status["users"]:
        report_status["users"].append(request.user._id)
        report_status["comments"].append({"u": request.user._id, "t": int(time.time()), "p": request.json["comment"]})
        if (request.remote_addr not in report_status["ips"]) and (request.user.state >= 1):
            report_status["ips"].append(request.remote_addr)
        meower.db.reports.find_one_and_replace({"_id": userdata["_id"]}, report_status)

    # Return payload
    return meower.resp("empty")
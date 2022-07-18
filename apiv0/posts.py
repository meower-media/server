from flask import Blueprint, request
from flask import current_app as meower
import time
from uuid import uuid4
import pymongo
import json

posts = Blueprint("posts_blueprint", __name__)

@posts.route("/<post_id>", methods=["GET", "DELETE"])
def get_post(post_id):
    # Check whether the client is authenticated
    meower.require_auth([5], scope="meower:posts:read_posts")

    # Get post
    post = meower.db["posts"].find_one({"_id": post_id, "isDeleted": False})
    if post is None:
        return meower.respond({"type": "notFound", "message": "Requested post was not found"}, 404, error=True)

    # Make sure the user has permission
    if not ((post["post_origin"] == "home") or (post["post_origin"] == "inbox")):
        chat_data = meower.db["chats"].find_one({"_id": post["post_origin"], "deleted": False})
        if (chat_data is None) or (request.session.user not in chat_data["members"]):
            return meower.respond({"type": "notFound", "message": "Requested post was not found"}, 404, error=True)
    elif post["post_origin"] == "inbox":
        if post["u"] != request.session.user:
            return meower.respond({"type": "notFound", "message": "Requested post was not found"}, 404, error=True)
        else:
            # Check whether the client is authenticated
            meower.require_auth([5], scope="meower:inbox:read_messages")

    if request.method == "GET":
        # Convert post data
        user = meower.User(meower, user_id=post["u"])
        if user.raw is None:
            return meower.respond({"type": "notFound", "message": "Requested post was not found"}, 404, error=True)
        else:
            post["u"] = user.profile

        # Return post
        return meower.respond(post, 200, error=False)
    elif request.method == "DELETE":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="meower:posts:edit_posts")

        # Delete post
        meower.db["posts"].update_one({"_id": post_id}, {"$set": {"isDeleted": True}})

        # Return payload
        return meower.respond({}, 200, error=False)

@posts.route("/<post_id>/comments", methods=["GET", "POST"])
def get_post_comments(post_id):
    # Check whether the client is authenticated
    meower.require_auth([5], scope="meower:posts:read_posts")

    # Get post
    post = meower.db["posts"].find_one({"_id": post_id, "isDeleted": False})
    if post is None:
        return meower.respond({"type": "notFound", "message": "Requested post was not found"}, 404, error=True)

    # Make sure the user has permission
    if not ((post["post_origin"] == "home") or (post["post_origin"] == "inbox")):
        chat_data = meower.db["chats"].find_one({"_id": post["post_origin"], "deleted": False})
        if (chat_data is None) or (request.session.user not in chat_data["members"]):
            return meower.respond({"type": "notFound", "message": "Requested post was not found"}, 404, error=True)
    elif post["post_origin"] == "inbox":
        if post["u"] != request.session.user:
            return meower.respond({"type": "notFound", "message": "Requested post was not found"}, 404, error=True)
        else:
            # Check whether the client is authenticated
            meower.require_auth([5], scope="meower:inbox:read_messages")

    if request.method == "GET":
        # Get page
        if not ("page" in request.args):
            page = 1
        else:
            page = int(request.args["page"])

        # Get index
        query_get = meower.db["posts"].find({"parent": post_id, "isDeleted": False}).skip((page-1)*25).limit(25).sort("t", pymongo.DESCENDING)
        pages_amount = (meower.db["posts"].count_documents({"parent": post_id, "isDeleted": False}) // 25) + 1

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
    elif request.method == "POST":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="meower:posts:create_posts", check_suspension=True)

        # Check for required data
        meower.check_for_json([{"id": "p", "t": str, "l_min": 1, "l_max": 360}])
    
        # Extract content for simplicity
        content = request.json["p"]

        # Check if account is spamming
        if meower.check_for_spam("comments-{0}".format(post_id), request.session.user, burst=10, seconds=5):
            return meower.respond({"type": "ratelimited", "message": "You are being ratelimited"}, 429, error=True)

        # Create post
        post_data = {
            "_id": str(uuid4()),
            "post_origin": post["post_origin"],
            "parent": post_id,
            "u": request.session.user,
            "p": content,
            "t": int(time.time()),
            "isDeleted": False
        }
        meower.db["posts"].insert_one(post_data)

        # Send notification to all users
        user = meower.User(meower, user_id=post["u"])
        post_data["u"] = user.profile
        meower.send_payload(json.dumps({"cmd": "new_post", "val": post_data}))

        # Return payload
        return meower.respond(post_data, 200, error=False)

@posts.route("/<post_id>/report", methods=["POST"])
def report_post(post_id):
    # Check whether the client is authenticated
    meower.require_auth([5], scope="meower:posts:edit_posts")

    # Check for required data
    meower.check_for_json([{"id": "comment", "t": str, "l_min": 1, "l_max": 360}])

    # Get post
    post = meower.db["posts"].find_one({"_id": post_id, "isDeleted": False})
    if post is None:
        return meower.respond({"type": "notFound", "message": "Requested post was not found"}, 404, error=True)

    # Add report
    report_status = meower.db["reports"].find_one({"_id": post_id})
    if report_status is None:
        report_status = {
            "_id": post_id,
            "type": 1,
            "users": [],
            "ips": [],
            "comments": [],
            "t": int(time.time()),
            "review_status": 0,
            "auto_censored": False
        }
    if request.session.user not in report_status["users"]:
        report_status["users"].append(request.session.user)
        report_status["comments"].append({"u": request.session.user, "t": int(time.time()), "p": request.json["comment"]})
        if request.remote_addr not in report_status["ips"]:
            report_status["ips"].append(request.remote_addr)
            if len(report_status["ips"]) > 3:
                report_status["auto_censored"] = True
                meower.db["posts"].update_one({"_id": post_id}, {"$set": {"isDeleted": True}})
    meower.db["users"].update_one({"_id": request.session.user}, report_status)

    # Return payload
    return meower.respond({}, 200, error=False)
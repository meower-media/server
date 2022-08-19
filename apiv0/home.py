from flask import Blueprint, request
from flask import current_app as meower
import time
from uuid import uuid4
import pymongo
import json

home = Blueprint("home_blueprint", __name__)

@home.route("/", methods=["GET", "POST"])
def get_home():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="meower:posts:read_posts")
    
    if request.method == "GET":
        # Get page
        if not ("page" in request.args):
            page = 1
        else:
            page = int(request.args["page"])

        # Get index
        query_get = meower.db.posts.find({"post_origin": "home", "parent": None, "isDeleted": False}).skip((page-1)*25).limit(25).sort("t", pymongo.DESCENDING)
        pages_amount = (meower.db.posts.count_documents({"post_origin": "home", "parent": None, "isDeleted": False}) // 25) + 1

        # Convert query get
        payload_posts = []
        for post in query_get:
            user = meower.User(meower, user_id=post["u"])
            if user.raw is None:
                meower.db.posts.update_one({"_id": post["_id"]}, {"$set": {"isDeleted": True}})
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
    elif request.method == "POST":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="meower:posts:create_posts")

        # Check for required data
        meower.check_for_json([{"id": "p", "t": str, "l_min": 1, "l_max": 360}])
    
        # Extract content for simplicity
        content = request.json["p"]

        # Check if account is spamming
        if meower.check_ratelimit("posts-home", request.user._id):
            return meower.resp(429)
        else:
            meower.ratelimit("posts-home", request.user._id, burst=3, seconds=15)

        # Create post
        post_data = {
            "_id": str(uuid4()),
            "post_origin": "home",
            "parent": None,
            "u": request.user._id,
            "p": content,
            "t": int(time.time()),
            "isDeleted": False
        }
        meower.db.posts.insert_one(post_data)

        # Send notification to all users
        post_data["u"] = request.user.profile
        #meower.send_payload(json.dumps({"cmd": "new_post", "val": post_data}))

        # Return payload
        return meower.resp(200, post_data)
from flask import Blueprint, request, abort
from flask import current_app as meower
import time
from uuid import uuid4
import pymongo
import json

home = Blueprint("home_blueprint", __name__)

@home.route("/", methods=["GET", "POST"])
def get_home():
    if request.method == "GET":
        # Get page
        if not ("page" in request.args):
            page = 1
        else:
            page = int(request.args["page"])

        # Get index
        query_get = meower.db["posts"].find({"post_origin": "home", "isDeleted": False}).skip((page-1)*25).limit(25).sort("t", pymongo.DESCENDING)
        pages_amount = (meower.db["posts"].count_documents({"post_origin": "home", "isDeleted": False}) // 25) + 1

        # Convert query get
        payload_posts = []
        for post in query_get:
            userdata = meower.db["usersv0"].find_one({"_id": post["u"]})
            if userdata is None:
                post["u"] = "Deleted"
            else:
                post["u"] = userdata["username"]
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
        meower.check_for_json(["p"])
    
        # Extract content for simplicity
        content = request.json["p"]

        # Check for bad datatypes and syntax
        if type(content) != str:
            return meower.respond({"type": "badDatatype"}, 400, error=True)
        elif len(content) > 360:
            return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
        elif meower.check_for_bad_chars_post(content):
            return meower.respond({"type": "illegalCharacters"}, 400, error=True)

        # Check if account is spamming
        if meower.check_for_spam("posts-home", request.session.user, burst=10, seconds=5):
            abort(429)

        # Create post
        post_data = {
            "_id": str(uuid4()),
            "post_origin": "home",
            "parent": None,
            "u": request.session.user,
            "p": content,
            "t": int(time.time()),
            "isDeleted": False
        }
        meower.db["posts"].insert_one(post_data)

        # Send notification to all users
        userdata = meower.db["usersv0"].find_one({"_id": request.session.user})
        post_data["username"] = userdata["username"]
        meower.send_payload(json.dumps({"cmd": "new_post", "val": post_data}))

        # Return payload
        return meower.respond(post_data, 200, error=False)
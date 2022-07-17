from flask import Blueprint, request
from flask import current_app as meower
import pymongo
from uuid import uuid4
import time
import json

chats = Blueprint("chats_blueprint", __name__)

@chats.route("/", methods=["GET", "PUT"])
def my_chats():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="meower:chats:access")

    if request.method == "GET":
        # Get index
        query_get = meower.db["chats"].find({"members": {"$all": [request.session.user]}, "deleted": False}).sort("nickname", pymongo.DESCENDING)

        # Convert query get
        payload_chat = []
        for chat_data in query_get:
            new_members = []
            for user_id in chat_data["members"]:
                user = meower.User(meower, user_id=user_id)
                if user.raw is not None:
                    new_members.append(user.profile)
            chat_data["members"] = new_members
            payload_chat.append(chat_data)

        # Create payload
        payload = {
            "chats": payload_chat,
            "page#": 1,
            "pages": 1
        }

        # Return payload
        return meower.respond(payload, 200, error=False)
    elif request.method == "PUT":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="meower:chats:edit")

        # Check for required data
        meower.check_for_json([{"id": "nickname", "t": str, "l_min": 1, "l_max": 20}])

        # Create chat
        chat_data = {
            "_id": str(uuid4()),
            "nickname": request.json["nickname"],
            "members": [request.session.user],
            "permissions": {request.session.user: 3},
            "public": False,
            "deleted": False
        }
        meower.db["chats"].insert_one(chat_data)

        # Convert members list
        new_members = []
        for user_id in chat_data["members"]:
            user = meower.User(meower, user_id=user_id)
            if user.raw is not None:
                new_members.append(user.profile)
        chat_data["members"] = new_members

        # Alert client that chat was created
        #app.meower.ws.sendPayload("update_config", "", username=request.session.user)

        # Return payload
        return meower.respond(chat_data, 200, error=False)

@chats.route("/<chat_id>", methods=["GET", "PATCH", "DELETE"])
def chat_data(chat_id):
    # Check whether the client is authenticated
    meower.require_auth([5], scope="meower:chats:access")

    # Get chat data
    chat_data = meower.db["chats"].find_one({"_id": chat_id, "deleted": False})

    # Check if chat exists
    if chat_data is None:
        return meower.respond({"type": "notFound", "message": "Requested chat was not found"}, 404, error=True)

    # Check if user is in chat
    if request.session.user not in chat_data["members"]:
        return meower.respond({"type": "notFound", "message": "Requested chat was not found"}, 404, error=True)
    
    if request.method == "GET":
        # Convert members list
        new_members = []
        for user_id in chat_data["members"]:
            user = meower.User(meower, user_id=user_id)
            if user.raw is not None:
                new_members.append(user.profile)
        chat_data["members"] = new_members

        # Return payload
        return meower.respond(chat_data, 200, error=False)
    elif request.method == "PATCH":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="meower:chats:edit")

        # Check if user has permission to edit chat
        if not (chat_data["permissions"][request.session.user] >= 3):
            return meower.respond({"type": "forbidden", "message": "You do not have permission to edit this chat"}, 403, error=True)

        # Update public status
        if "public" in request.json:
            if type(request.json["public"]) == bool:
                chat_data["public"] = request.json["public"]

        # Update owner
        if "owner" in request.json:
            if type(request.json["owner"]) == str:
                user = meower.User(meower, username=request.json["owner"])
                if user.raw is not None:
                    return meower.respond({"type": "notFound", "message": "Requested user was not found"}, 404, error=True)
                elif user._id not in chat_data["members"]:
                    return meower.respond({"type": "notFound", "message": "Requested user was not found"}, 404, error=True)
                elif user._id == request.session.user:
                    return meower.respond({"type": "cannotChangeOwnerToSelf", "message": "You cannot change the owner to yourself"}, 400, error=True)
                else:
                    chat_data["permissions"][user._id] = 3
                    chat_data["permissions"][request.session.user] = 1

        # Update chat
        meower.db["chats"].update_one({"_id": chat_id}, {"$set": {"public": chat_data["public"], "permissions": chat_data["permissions"]}})

        # Convert members list
        new_members = []
        for user_id in chat_data["members"]:
            user = meower.User(meower, user_id=user_id)
            if user.raw is not None:
                new_members.append(user.profile)
        chat_data["members"] = new_members

        # Return payload
        return meower.respond(chat_data, 200, error=False)
    elif request.method == "DELETE":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="meower:chats:edit")

        if chat_data["permissions"][request.session.user] >= 3:
            meower.db["chats"].update_one({"_id": chat_id}, {"$set": {"deleted": True}})
            return meower.respond({}, 200, error=False)
        else:
            chat_data["members"].remove(request.session.user)
            meower.db["chats"].update_one({"_id": chat_id}, {"$set": {"members": chat_data["members"]}})
            return meower.respond({}, 200, error=False)

@chats.route("/<chat_id>/members", methods=["PUT", "PATCH", "DELETE"])
def add_member(chat_id):
    # Check whether the client is authenticated
    meower.require_auth([5], scope="meower:chats:access")

    # Check for required data
    meower.check_for_json([{"id": "username", "t": str, "l_min": 1, "l_max": 20}])

    # Get chat data
    chat_data = meower.db["chats"].find_one({"_id": chat_id, "deleted": False})

    # Check if chat exists
    if chat_data is None:
        return meower.respond({"type": "notFound", "message": "Requested chat was not found"}, 404, error=True)

    # Check if user is in chat
    if request.session.user not in chat_data["members"]:
        return meower.respond({"type": "notFound", "message": "Requested chat was not found"}, 404, error=True)

    # Get requested user
    user = meower.User(meower, username=request.json["username"])
    if user.raw is None:
        return meower.respond({"type": "notFound", "message": "Requested user was not found"}, 404, error=True)
    
    if request.method == "PUT":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="meower:chats:edit")

        # Make sure user is not blocked
        if request.session.user in user.security["blocked"]:
            return meower.respond({"type": "notFound", "message": "Requested user does not exist"}, 404, error=True)

        # Add user to chat
        if user._id not in chat_data["members"]:
            chat_data["members"].append(user._id)
            chat_data["permissions"][user._id] = 1

        # Update chat
        meower.db["chats"].update_one({"_id": chat_id}, {"$set": {"members": chat_data["members"], "permissions": chat_data["permissions"]}})

        # Return payload
        return meower.respond({}, 200, error=False)
    elif request.method == "PATCH":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="meower:chats:edit")

        # Check for required data
        meower.check_for_json([{"id": "level", "t": int, "r_min": 1, "r_max": 2}])

        # Check if user is in chat
        if user._id not in chat_data["members"]:
            return meower.respond({"type": "userNotInChat", "message": "Requested user not in chat"}, 404, error=True)

        # Check if the user has permission to edit user permissions
        if not ((request.session.user != user._id) and (chat_data["permissions"][request.session.user] >= 3)):
            return meower.respond({"type": "forbidden", "message": "You do not have permission to edit this user"}, 403, error=True)

        # Update user permissions
        chat_data["permissions"][user._id] = request.json["level"]

        # Update chat
        meower.db["chats"].update_one({"_id": chat_id}, {"$set": {"permissions": chat_data["permissions"]}})

        # Return payload
        return meower.respond({}, 200, error=False)
    elif request.method == "DELETE":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="meower:chats:edit")

        # Check if user is in chat
        if user._id not in chat_data["members"]:
            return meower.respond({"type": "userNotInChat", "message": "Requested user not in chat"}, 404, error=True)

        # Check if the user has permission to remove the user
        if not ((request.session.user != user._id) and (chat_data["permissions"][request.session.user] >= 2) and (chat_data["permissions"][request.session.user] > chat_data["permissions"][user._id])):
            return meower.respond({"type": "forbidden", "message": "You do not have permission to remove this user"}, 403, error=True)

        # Remove user from chat
        chat_data["members"].remove(user._id)
        del chat_data["permissions"][user._id]

        # Update chat
        meower.db["chats"].update_one({"_id": chat_id}, {"$set": {"members": chat_data["members"], "permissions": chat_data["permissions"]}})

        # Return payload
        return meower.respond({}, 200, error=False)

@chats.route("/<chat_id>/posts", methods=["GET", "POST"])
def chat_posts(chat_id):
    # Check whether the client is authenticated
    meower.require_auth([5], scope="meower:chats:access")

    # Get chat data
    chat_data = meower.db["chats"].find_one({"_id": chat_id, "deleted": False})

    # Check if chat exists
    if chat_data is None:
        return meower.respond({"type": "notFound", "message": "Requested chat does not exist"}, 404, error=True)

    # Check if user is in chat
    if request.session.user not in chat_data["members"]:
        return meower.respond({"type": "notFound", "message": "Requested chat does not exist"}, 404, error=True)

    if request.method == "GET":
        # Get page
        if not ("page" in request.args):
            page = 1
        else:
            page = int(request.args["page"])

        # Get index
        query_get = meower.db["posts"].find({"post_origin": chat_id, "parent": None, "isDeleted": False}).skip((page-1)*25).limit(25).sort("t", pymongo.DESCENDING)
        pages_amount = (meower.db["posts"].count_documents({"post_origin": chat_id, "parent": None, "isDeleted": False}) // 25) + 1

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
        if meower.check_for_spam("posts-{0}".format(chat_id), request.session.user, burst=10, seconds=5):
            return meower.respond({"type": "ratelimited", "message": "You are being ratelimited"}, 429, error=True)

        # Create post
        post_data = {
            "_id": str(uuid4()),
            "post_origin": chat_id,
            "parent": None,
            "u": request.session.user,
            "p": content,
            "t": int(time.time()),
            "isDeleted": False
        }
        meower.db["posts"].insert_one(post_data)

        # Send notification to all users
        user = meower.User(meower, user_id=request.session.user)
        post_data["u"] = user.profile
        meower.send_payload(json.dumps({"cmd": "new_post", "val": post_data}))

        # Return payload
        return meower.respond(post_data, 200, error=False)
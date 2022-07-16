from flask import Blueprint, request, abort
from flask import current_app as meower
import pymongo
from uuid import uuid4

chats = Blueprint("chats_blueprint", __name__)

@chats.route("/", methods=["GET", "PUT"])
def my_chats():
    if request.method == "GET":
        # Get index
        query_get = meower.db["chats"].find({"members": {"$all": [request.session.user]}, "deleted": False}).sort("nickname", pymongo.DESCENDING)

        # Convert query get
        payload_chat = []
        for chat in query_get:
            for user_id in chat["members"]:
                user = meower.User(meower, user_id)
                chat["members"].remove(user_id)
                if user is not None:
                    chat["members"].append(user.profile)
            payload_chat.append(chat)

        # Create payload
        payload = {
            "chats": payload_chat,
            "page#": 1,
            "pages": 1
        }

        # Return payload
        return meower.respond(payload, 200, error=False)
    elif request.method == "PUT":
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
        for user_id in chat_data["members"]:
            user = meower.User(meower, user_id)
            chat_data["members"].remove(user_id)
            if user is not None:
                chat_data["members"].append(user.profile)

        # Alert client that chat was created
        #app.meower.ws.sendPayload("update_config", "", username=request.session.user)

        # Return payload
        return meower.respond(chat_data, 200, error=False)

@chats.route("/<chatid>", methods=["GET", "PATCH", "DELETE"])
def chat_data(chatid):
    # Get chat data
    chat_data = meower.db["chats"].find_one({"_id": chatid, "deleted": False})

    # Check if chat exists
    if chat_data is None:
        return meower.respond({"type": "notFound", "message": "Requested chat was not found"}, 404, error=True)

    # Check if user is in chat
    if request.session.user not in chat_data["members"]:
        return meower.respond({"type": "notFound", "message": "Requested chat was not found"}, 404, error=True)
    
    if request.method == "GET":
        # Convert members list
        for user_id in chat_data["members"]:
            user = meower.User(meower, user_id)
            chat_data["members"].remove(user_id)
            if user is not None:
                chat_data["members"].append(user.profile)

        # Return payload
        return meower.respond(chat_data, 200, error=False)
    elif request.method == "PATCH":
        # Update public status
        if "public" in request.json:
            if type(request.json["public"]) == bool:
                chat_data["public"] = request.json["public"]
        meower.db["chats"].update_one({"_id": chatid}, {"$set": {"public": chat_data["public"]}})

        # Convert members list
        for user_id in chat_data["members"]:
            user = meower.User(meower, user_id)
            chat_data["members"].remove(user_id)
            if user is not None:
                chat_data["members"].append(user.profile)

        # Return payload
        return meower.respond(chat_data, 200, error=False)
    elif request.method == "DELETE":
        if chat_data["permissions"][request.session.user] >= 3:
            meower.db["chats"].update_one({"_id": chatid}, {"$set": {"deleted": True}})
            return meower.respond({}, 200, error=False)
        else:
            chat_data["members"].remove(request.session.user)
            meower.db["chats"].update_one({"_id": chatid}, {"$set": {"members": chat_data["members"]}})
            return meower.respond({}, 200, error=False)

@chats.route("/<chatid>/members", methods=["PUT", "PATCH", "DELETE"])
def add_member(chatid):
    # Check for required data
    meower.check_for_json([{"id": "username", "t": str, "l_min": 1, "l_max": 20}])

    # Get user data
    user = meower.User(meower, username=request.json["username"])
    if user is None:
        return meower.respond({"type": "notFound", "message": "Requested user does not exist"}, 404, error=True)

    # Get chat data
    chat_data = meower.db["chats"].find_one({"_id": chatid, "deleted": False})

    # Check if chat exists
    if chat_data is None:
        return meower.respond({"type": "notFound", "message": "Requested chat does not exist"}, 404, error=True)

    # Check if user is in chat
    if request.session.user not in chat_data["members"]:
        return meower.respond({"type": "notFound", "message": "Requested chat does not exist"}, 404, error=True)
    
    if request.method == "PUT":
        # Check if user is in chat
        if user._id in chat_data["members"]:
            return meower.respond({"type": "alreadyExists", "message": "User is already in chat"}, 400, error=True)

        # Add user to chat
        chat_data["members"].append(user._id)
        chat_data["permissions"][user._id] = 1

        # Update chat
        meower.db["chats"].update_one({"_id": chatid}, {"$set": {"members": chat_data["members"]}})

        # Return payload
        return meower.respond({}, 200, error=False)
    elif request.method == "PATCH":
        pass
    elif request.method == "DELETE":
        # Check if user is in chat
        if user._id not in chat_data["members"]:
            return meower.respond({"type": "doesNotExist", "message": "User does not exist in chat"}, 400, error=True)

        # Check if the user has permission to remove the user
        if not ((request.session.user != user._id) and (chat_data["permissions"][request.session.user] >= 2) and (chat_data["permissions"][request.session.user] > chat_data["permissions"][user._id])):
            return meower.respond({"type": "forbidden", "message": "You do not have permission to remove this user"}, 403, error=True)

        # Remove user from chat
        chat_data["members"].remove(user._id)
        del chat_data["permissions"][user._id]

        # Update chat
        meower.db["chats"].update_one({"_id": chatid}, {"$set": {"members": chat_data["members"]}})

        # Return payload
        return meower.respond({}, 200, error=False)
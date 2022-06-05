from flask import Blueprint, request, abort
from flask import current_app as app

chats = Blueprint("chats_blueprint", __name__)

@chats.route("/create", methods=["POST"])
def create_chat():
    if not ("nickname" in request.form):
        return app.respond({"type": "missingField"}, 400, error=True)

    # Create chat
    chatdata = {
        "nickname": request.form.get("nickname"),
        "members": [request.session.user],
        "permissions": {request.session.user: 3},
        "isPublic": False,
        "isDeleted": False
    }
    file_write = app.meower.files.create_item("chats", app.meower.supporter.uuid(), chatdata)
    if not file_write:
        abort(500)

    # Alert client that chat was created
    app.meower.ws.sendPayload("update_config", "", username=request.session.user)

    return app.respond(chatdata, 200, error=False)

@chats.route("/<chatid>", methods=["GET", "DELETE"])
def get_chat_data(chatid):
    # Get chat data
    file_read, chatdata = app.meower.files.load_item("chats", chatid)
    if not file_read:
        abort(404)
    
    if request.method == "GET":
        if not (request.session.user in chatdata["members"] or chatdata["isPublic"]):
            abort(403)
        return app.respond(chatdata, 200, error=False)
    elif request.method == "DELETE":
        if (request.session.user in chatdata["members"]) and (chatdata["permissions"][request.session.user] == 3):
            file_write = app.meower.files.delete_item("chats", chatid)
            if not file_write:
                abort(500)
        elif request.session.user in chatdata["members"]:
            chatdata["members"].remove(request.session.user)
            file_write = app.meower.files.write_item("chats", chatid, chatdata)
            if not file_write:
                abort(500)
        else:
            abort(403)

        return app.respond({}, 200, error=False)

@chats.route("/<chatid>/members", methods=["PUT", "PATCH", "DELETE"])
def add_member(chatid, user):
    if request.method == "PUT":
        # Get chat data
        file_read, chatdata = app.meower.files.load_item("chats", chatid)
        if not file_read:
            abort(404)

        # Check if user is in chat
        if not (request.session.user in chatdata["members"]):
            abort(403)

        # Check for bad datatypes and syntax
        if len(user) > 20:
            return app.respond({"type": "fieldTooLarge"}, 400, error=True)
        elif app.meower.supporter.checkForBadCharsUsername(user):
            return app.respond({"type": "illegalCharacters"}, 400, error=True)

        # Check if user exists
        file_read, userdata = app.meower.files.load_item("users", user)
        if not file_read:
            return app.respond({"type": "userNotFound"}, 400, error=True)

        # Add user to chat
        if not (user in chatdata["members"]):
            chatdata["members"].append(user)
            chatdata["added_by"][user] = request.session.user
            file_write = app.meower.files.write_item("chats", chatid, chatdata)
            if not file_write:
                abort(500)

        return app.respond({}, 200, error=False)
    elif request.method == "DELETE":
        # Get chat data
        file_read, chatdata = app.meower.files.load_item("chats", chatid)
        if not file_read:
            abort(404)

        # Check if user is owner
        if request.session.user != chatdata["owner"]:
            abort(403)

        # Check for bad datatypes and syntax
        if len(user) > 20:
            return app.respond({"type": "fieldTooLarge"}, 400, error=True)
        elif app.meower.supporter.checkForBadCharsUsername(user):
            return app.respond({"type": "illegalCharacters"}, 400, error=True)

        # Check if user is in chat
        if not (user in chatdata["members"]):
            return app.respond({"type": "userNotFound"}, 400, error=True)

        # Remove user from chat
        chatdata["members"].remove(user)
        file_write = app.meower.files.write_item("chats", chatid, chatdata)
        if not file_write:
            abort(500)

        return app.respond({}, 200, error=False)
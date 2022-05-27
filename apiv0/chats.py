from flask import Blueprint, request, abort
from flask import current_app as app

chats = Blueprint("chats_blueprint", __name__)

@chats.route("/", methods=["GET"])
def get_chats():
    if not request.authed:
        abort(401)
    
    if not ("page" in request.args):
        page = 1
    else:
        page = int(request.args.get("page"))

    payload = app.meower.files.find_items("chats", {"members": {"$all": [request.auth]}}, truncate=True, page=page)

    payload["all_chats"] = []
    for chatid in payload["index"]:
        file_read, chatdata = app.meower.files.load_item("chats", chatid)
        if file_read:
            payload["all_chats"].append(chatdata)

    return app.respond(payload, 200, error=False)

@chats.route("/create", methods=["POST"])
def create_chat():
    if not request.authed:
        abort(401)

    if not ("nickname" in request.form):
        return app.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    nickname = request.form.get("nickname")

    # Check for bad datatypes and syntax
    if not (type(nickname) == str):
        return app.respond({"type": "badDatatype"}, 400, error=True)
    elif len(nickname) > 20:
        return app.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif app.meower.supporter.checkForBadCharsPost(nickname):
        return app.respond({"type": "illegalCharacters"}, 400, error=True)

    file_write = app.meower.files.create_item("chats", app.meower.supporter.uuid(), {
        "nickname": nickname,
        "owner": request.auth,
        "members": [request.auth],
        "added_by": {request.auth: request.auth},
        "isDeleted": False
    })

    if not file_write:
        abort(500)

    return app.respond({}, 200, error=False)

@chats.route("/mychat/<chatid>", methods=["GET", "DELETE"])
def get_chat_data(chatid):
    if not request.authed:
        abort(401)

    # Get chat data
    file_read, chatdata = app.meower.files.load_item("chats", chatid)
    if not file_read:
        abort(404)
    
    if request.method == "GET":
        if not (request.auth in chatdata["members"]):
            abort(403)
        
        return app.respond(chatdata, 200, error=False)
    elif request.method == "DELETE":
        if request.auth != chatdata["owner"]:
            abort(403)
        else:
            file_write = app.meower.files.delete_item("chats", chatid)
            if not file_write:
                abort(500)
            
            return app.respond({}, 200, error=False)
from flask import Blueprint, request, abort
from flask import current_app as app

auth = Blueprint("authentication_blueprint", __name__)

@auth.before_app_request
def check_auth():
    request.auth = None
    request.authed = False
    request.session_data = None

    if "token" in request.headers:
        token = request.headers.get("token")
    
    try:
        token_data = app.meower.accounts.get_token(token)

        request.auth = token_data["u"]
        request.authed = True
        request.session_data = {
            "id": token_data["_id"],
            "expires": token_data["expires"],
            "u": token_data["u"]
        }
    except:
        pass

@auth.route("/login", methods=["POST"])
def login():
    if not (("username" in request.form) and ("password" in request.form)):
        return app.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    username = request.form.get("username")
    password = request.form.get("password")

    # Check for bad datatypes and syntax
    if not ((username == str) and (password == str)):
        return app.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(username) > 20) or (len(password) > 72):
        return app.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif (app.meower.supporter.checkForBadCharsUsername(username)) or (app.meower.supporter.checkForBadCharsPost(password)):
        return app.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check account flags and password
    file_check, file_read, flags = app.meower.accounts.get_flags(username)
    if flags["locked"]:
        return app.respond({"type": "accountLocked"}, 401, error=True)
    elif flags["perm_locked"]:
        return app.respond({"type": "accountPermLocked"}, 401, error=True)
    elif flags["dormant"]:
        return app.respond({"type": "accountDormant"}, 401, error=True)
    elif flags["deleted"]:
        return app.respond({"type": "accountDeleted"}, 401, error=True)
    elif (app.meower.accounts.authenticate(username, password) != (True, True, True)):
        return app.respond({"type": "invalidPassword"}, 401, error=True)
    elif flags["banned"]:
        return app.respond({"type": "accountBanned"}, 401, error=True)
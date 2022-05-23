from flask import Blueprint, request, abort
from flask import current_app as app

auth = Blueprint("authentication_blueprint", __name__)

class User:
    def __init__(self, username):
        file_check, file_read, userdata = app.meower.accounts.get_account(username)
        if file_check and file_read:
            self.id = username
            self.username = username

@auth.before_app_request
def check_auth():
    request.session_data = None
    request.auth = None
    request.authed = False

    if "Authentication" in request.headers:
        if "Bearer" in request.headers.get("Authentication"):
            token = request.headers.get("Authentication").replace("Bearer ", "")
        else:
            token = request.headers.get("Authentication")
    elif "Token" in request.headers:
        token = request.headers.get("Token")
    elif "Auth" in request.headers:
        token = request.headers.get("Auth")
    
    tokendata = app.meower.files.find_items("keys", {"key": token})

    if (tokendata["expires"] == None) or (not (tokendata["expires"] > app.meower.supporter.timestamp(7))):
        file_check, file_read, Flags = app.meower.accounts.get_flags(tokendata["u"])
        if file_check and file_read:
            if not (Flags["locked"] or Flags["perm_locked"] or Flags["banned"] or Flags["dormant"] or Flags["pending_deletion"] or Flags["deleted"]):
                request.session_data = {
                    "id": tokendata["_id"],
                    "expires": tokendata["expires"],
                    "username": tokendata["u"],
                    "flags": Flags
                }
                request.auth = tokendata["u"]
                request.authed = True

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
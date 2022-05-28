from flask import Blueprint, request, abort
from flask import current_app as app

auth = Blueprint("authentication_blueprint", __name__)

@auth.before_app_request
def check_auth():
    request.auth = None
    request.authed = False
    request.session_data = None

    if "Authorization" in request.headers:
        token = request.headers.get("Authorization")
        file_read, token_data = app.meower.accounts.get_token(token)
        if file_read:
            request.auth = token_data["u"]
            request.authed = True
            request.session_data = token_data.copy()
            del request.session_data["token"]

@auth.route("/", methods=["GET", "PATCH"])
def get_me():
    if not request.authed:
        abort(401)
    
    if request.method == "GET":
        file_read, userdata = app.meower.accounts.get_account(request.auth)
        if not file_read:
            abort(500)

        return app.respond(userdata["client_userdata"], 200, error=False)
    elif request.method == "PATCH":
        newdata = {}
        for key, value in request.form.items():
            newdata[key] = value
        
        file_write = app.meower.accounts.update_config(request.auth, newdata)
        if not file_write:
            abort(500)

        if request.auth in app.meower.cl.getUsernames():
            app.meower.commands.sendLivePayload(request.auth, "update_config", "")
        
        return app.respond({}, 200, error=False)

@auth.route("/login", methods=["POST"])
def login():
    if not (("username" in request.form) and ("password" in request.form)):
        return app.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    username = request.form.get("username")
    password = request.form.get("password")

    # Check for bad datatypes and syntax
    if not ((type(password) == str) and (type(password) == str)):
        return app.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(username) > 20) or (len(password) > 72):
        return app.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif (app.meower.supporter.checkForBadCharsUsername(username)) or (app.meower.supporter.checkForBadCharsPost(password)):
        return app.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check account flags and password
    file_read, userdata = app.meower.accounts.get_account(username)
    if not file_read:
        return app.respond({"type": "accountDoesNotExist"}, 401, error=True)
    elif userdata["flags"]["locked"]:
        return app.respond({"type": "accountLocked", "expires": userdata["userdata"]["flags"]["locked_until"]-app.meower.supporter.timestamp(6)}, 401, error=True)
    elif userdata["flags"]["dormant"]:
        return app.respond({"type": "accountDormant"}, 401, error=True)
    elif (app.meower.accounts.check_password(username, password) != (True, True)):
        return app.respond({"type": "invalidPassword"}, 401, error=True)
    elif userdata["flags"]["deleted"]:
        return app.respond({"type": "accountDeleted"}, 401, error=True)
    elif userdata["flags"]["banned"]:
        return app.respond({"type": "accountBanned", "expires": userdata["userdata"]["flags"]["banned_until"]-app.meower.supporter.timestamp(6)}, 401, error=True)
    
    # Restore account if it's pending deletion
    if userdata["flags"]["pending_deletion"]:
        app.meower.accounts.cancel_deletion(username)

    # Generate new token and return to user
    file_write, token = app.meower.accounts.create_token(username, expiry=2592000, type=1)
    if file_write:
        return app.respond({"token": token, "type": "Bearer"}, 200, error=False)
    else:
        abort(500)

@auth.route("/create", methods=["POST"])
def create_account():
    if not (("username" in request.form) and ("password" in request.form)):
        return app.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    username = request.form.get("username")
    password = request.form.get("password")

    # Check for bad datatypes and syntax
    if not ((type(password) == str) and (type(password) == str)):
        return app.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(username) > 20) or (len(password) > 72):
        return app.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif (app.meower.supporter.checkForBadCharsUsername(username)) or (app.meower.supporter.checkForBadCharsPost(password)):
        return app.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check if account exists
    if app.meower.files.does_item_exist("usersv0", username):
        return app.respond({"type": "accountAlreadyExists"}, 401, error=True)

    # Create userdata
    file_write = app.meower.accounts.create_account(username, password)
    if not file_write:
        abort(500)

    # Generate new token and return to user
    file_write, token = app.meower.accounts.create_token(username, expiry=2592000, type=1)
    if file_write:
        return app.respond({"token": token, "type": "Bearer"}, 200, error=False)
    else:
        abort(500)

@auth.route("/login_code", methods=["POST"])
def auth_login_code():
    if not request.authed:
        abort(401)
    
    if not ("code" in request.form):
        return app.respond({"type": "missingField"}, 400, error=True)
    
    # Extract code for simplicity
    code = request.form.get("code")

    # Check for bad datatypes and syntax
    if not (type(code) == str):
        return app.respond({"type": "badDatatype"}, 400, error=True)
    elif len(code) > 6:
        return app.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif app.meower.supporter.checkForBadCharsPost(code):
        return app.respond({"type": "illegalCharacters"}, 400, error=True)
    
    # Check if code exists
    if not (code in app.meower.cl.statedata["ulist"]["login_codes"]):
        return app.respond({"type": "codeDoesNotExist"}, 400, error=True)
    
    # Create new token
    file_write, token = app.meower.accounts.create_token(request.auth, expiry=2592000, type=1)
    if not file_write:
        abort(500)

    # Send token to client
    app.meower.commands.sendLivePayload(app.meower.cl.statedata["ulist"]["login_codes"][code], "login_code", token)

    # Delete login code
    app.meower.supporter.modify_client_statedata(app.meower.cl.statedata["ulist"]["login_codes"][code], "login_code", None)
    del app.meower.cl.statedata["ulist"]["login_codes"][code]

    return app.respond({}, 200, error=False)

@auth.route("/session", methods=["GET", "DELETE"])
def current_session():
    if not request.authed:
        abort(401)
    
    session_data = request.session_data.copy()
    session_data["authed"] = request.authed

    return app.respond(session_data, 200, error=False)

@auth.route("/all_sessions", methods=["DELETE"])
def all_sessions():
    if not request.authed:
        abort(401)
    
    if request.method == "DELETE":
        app.meower.files.delete_all("keys", {"u": request.auth, "type": 1})

        if request.auth in app.meower.cl.getUsernames():
            app.meower.commands.abruptLogout(request.auth, "session_expired")

        return app.respond({}, 200, error=False)

@auth.route("/mfa_setup", methods=["GET", "POST"])
def mfa_setup():

    ## TO BE CONTINUED

    if not request.authed:
        abort(401)

    if request.method == "GET":
        # Generate new token and return to user
        file_write, token = app.meower.accounts.create_token(request.auth, expiry=600, type=2)
        if file_write:
            return app.respond({"token": token, "type": "Bearer"}, 200, error=False)
        else:
            abort(500)
    elif request.method == "POST":
        if not (("token" in request.form) and ("code" in request.form)):
            return app.respond({"type": "missingField"}, 400, error=True)
        
        # Extract token and code for simplicity
        token = request.form.get("token")
        code = request.form.get("code")

        # Check for bad datatypes and syntax
        if not ((type(token) == str) and (type(code) == str)):
            return app.respond({"type": "badDatatype"}, 400, error=True)
        elif (len(token) > 100) or (len(code) > 6):
            return app.respond({"type": "fieldTooLarge"}, 400, error=True)
        elif app.meower.supporter.checkForBadCharsPost(code):
            return app.respond({"type": "illegalCharacters"}, 400, error=True)
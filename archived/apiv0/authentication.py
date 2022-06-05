from flask import Blueprint, request, abort
from flask import current_app as app
from user_agents import parse as parse_ua
import secrets
import string

auth = Blueprint("authentication_blueprint", __name__)

@auth.route("/", methods=["GET", "PATCH", "DELETE"])
def get_me():
    app.meower.accounts.renew_token(request.session_data["token"], device={
        "ip": request.remote_addr,
        "ua": request.headers.get("user-agent"),
        "os": {
            "name": request.parsed_user_agent.os.family,
            "version": request.parsed_user_agent.os.version_string
        },
        "browser": {
            "name": request.parsed_user_agent.browser.family,
            "version": request.parsed_user_agent.browser.version_string
        },
        "client": request.parsed_user_agent.client
    })

    if request.method == "GET":
        file_read, userdata = app.meower.accounts.get_account(request.session.user)
        if not file_read:
            abort(500)

        return app.respond(userdata["client_userdata"], 200, error=False)
    elif request.method == "PATCH":
        newdata = {}
        for key, value in request.form.items():
            newdata[key] = value
        
        file_write = app.meower.accounts.update_config(request.session.user, newdata)
        if not file_write:
            abort(500)

        app.meower.ws.sendPayload(request.session.user, "update_config", "", username=request.session.user)
        
        return app.respond({}, 200, error=False)
    elif request.method == "DELETE":
        file_read, userdata = app.meower.accounts.get_account(request.session.user)
        if not file_read:
            abort(500)
        
        if type(userdata["userdata"]["mfa_secret"]) == str:
            if app.meower.accounts.check_mfa(request.session.user, request.form.get("mfa_code")) != (True, True):
                return app.respond({"type": "mfaCodeInvalid"}, 401, error=True)
        
        file_write = app.meower.accounts.update_config(request.session.user, {"mfa_secret": None, "mfa_recovery": None, "flags.delete_after": app.meower.timestamp(6)+86400}, forceUpdate=True)
        if not file_write:
            abort(500)

        app.meower.files.delete_all("keys", {"u": request.session.user})
        app.meower.commands.abruptLogout(request.session.user, "account_deleted")

        return app.respond({}, 200, error=False)

@auth.route("/login", methods=["POST"])
def login():
    if not (("username" in request.form) and ("password" in request.form)):
        return app.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    username = request.form.get("username").strip()
    password = request.form.get("password").strip()

    # Check for bad datatypes and syntax
    if not ((type(username) == str) and (type(password) == str)):
        return app.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(username) > 20) or (len(password) > 72):
        return app.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif app.meower.supporter.checkForBadCharsUsername(username):
        return app.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check account flags and password
    file_read, userdata = app.meower.accounts.get_account(username)
    if not file_read:
        return app.respond({"type": "accountDoesNotExist"}, 401, error=True)
    elif userdata["flags"]["locked"]:
        return app.respond({"type": "accountLocked", "expires": userdata["userdata"]["flags"]["locked_until"]-app.meower.timestamp(6)}, 401, error=True)
    elif userdata["flags"]["dormant"]:
        return app.respond({"type": "accountDormant"}, 401, error=True)
    elif (app.meower.accounts.check_password(username, password) != (True, True)):
        return app.respond({"type": "invalidPassword"}, 401, error=True)
    elif userdata["flags"]["deleted"]:
        return app.respond({"type": "accountDeleted"}, 401, error=True)
    elif userdata["flags"]["banned"]:
        return app.respond({"type": "accountBanned", "expires": userdata["userdata"]["flags"]["banned_until"]-app.meower.timestamp(6)}, 401, error=True)
    
    # Restore account if it's pending deletion
    if userdata["flags"]["pending_deletion"]:
        file_write = app.meower.accounts.update_config(username, {"flags.delete_after": None}, forceUpdate=True)
        if not file_write:
            abort(500)

    # Generate new token and return to user
    if userdata["userdata"]["mfa_secret"] != None:
        # MFA only token
        token_type = "MFA"
        file_write, token = app.meower.accounts.create_token(username, expiry=600, type=2)
        if not file_write:
            abort(500)
    else:
        # Full account token
        token_type = "Bearer"
        file_write, token = app.meower.accounts.create_token(username, expiry=2592000, type=1, device={
            "ip": request.remote_addr,
            "ua": request.headers.get("user-agent"),
            "os": {
                "name": request.parsed_user_agent.os.family,
                "version": request.parsed_user_agent.os.version_string
            },
            "browser": {
                "name": request.parsed_user_agent.browser.family,
                "version": request.parsed_user_agent.browser.version_string
            },
            "client": request.parsed_user_agent.client
        })
        if not file_write:
            abort(500)

    return app.respond({"token": token, "type": token_type}, 200, error=False)

@auth.route("/login/mfa", methods=["POST"])
def login_mfa():
    if not (("token" in request.form) and ("code" in request.form)):
        return app.respond({"type": "missingField"}, 400, error=True)
    
    # Extract token and MFA code for simplicity
    token = request.form.get("token")
    code = request.form.get("code")

    # Check for bad datatypes and syntax
    if not ((type(token) == str) and (type(code) == str)):
        return app.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(token) > 100) or (len(code) > 6):
        return app.respond({"type": "fieldTooLarge"}, 400, error=True)

    # Get user from token
    file_read, token_data = app.meower.accounts.get_token(token)
    if (not file_read) or (token_data["type"] != 2):
        return app.respond({"type": "tokenInvalid"}, 401, error=True)
    else:
        username = token_data["u"]

    # Get account and MFA secret
    file_read, userdata = app.meower.accounts.get_account(username)
    if not file_read:
        return app.respond({"type": "tokenInvalid"}, 401, error=True)
    elif userdata["userdata"]["mfa_secret"] is None:
        return app.respond({"type": "tokenInvalid"}, 401, error=True)

    # Check MFA code
    if app.meower.accounts.check_mfa(username, code) != (True, True):
        return app.respond({"type": "mfaInvalid"}, 401, error=True)

    # Delete temporary MFA token
    app.meower.accounts.delete_token(token)

    # Generate full account token and return to user
    file_write, token = app.meower.accounts.create_token(username, expiry=2592000, type=1, device={
        "ip": request.remote_addr,
        "ua": request.headers.get("user-agent"),
        "os": {
            "name": request.parsed_user_agent.os.family,
            "version": request.parsed_user_agent.os.version_string
        },
        "browser": {
            "name": request.parsed_user_agent.browser.family,
            "version": request.parsed_user_agent.browser.version_string
        },
        "client": request.parsed_user_agent.client
    })
    if not file_write:
        abort(500)
    
    return app.respond({"token": token, "type": "Bearer"}, 200, error=False)

@auth.route("/create", methods=["POST"])
def create_account():
    if not (("username" in request.form) and ("password" in request.form)):
        return app.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    username = request.form.get("username").strip()
    password = request.form.get("password").strip()

    # Check for bad datatypes and syntax
    if not ((type(password) == str) and (type(password) == str)):
        return app.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(username) > 20) or (len(password) > 72):
        return app.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif app.meower.supporter.checkForBadCharsUsername(username):
        return app.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check if account exists
    if app.meower.files.does_item_exist("usersv0", username):
        return app.respond({"type": "accountAlreadyExists"}, 401, error=True)

    # Create userdata
    file_write = app.meower.accounts.create_account(username, password)
    if not file_write:
        abort(500)

    # Generate new token and return to user
    file_write, token = app.meower.accounts.create_token(username, expiry=2592000, type=1, device={
        "ip": request.remote_addr,
        "ua": request.headers.get("user-agent"),
        "os": {
            "name": request.parsed_user_agent.os.family,
            "version": request.parsed_user_agent.os.version_string
        },
        "browser": {
            "name": request.parsed_user_agent.browser.family,
            "version": request.parsed_user_agent.browser.version_string
        },
        "client": request.parsed_user_agent.client
    })
    if file_write:
        return app.respond({"token": token, "type": "Bearer"}, 200, error=False)
    else:
        abort(500)

@auth.route("/login_code", methods=["POST"])
def auth_login_code():
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
    file_write, token = app.meower.accounts.create_token(request.session.user, expiry=2592000, type=1)
    if not file_write:
        abort(500)

    # Send token to client
    app.meower.ws.sendPayload(app.meower.cl.statedata["ulist"]["login_codes"][code], "login_code", token)

    # Delete login code
    app.meower.supporter.modify_client_statedata(app.meower.cl.statedata["ulist"]["login_codes"][code], "login_code", None)
    del app.meower.cl.statedata["ulist"]["login_codes"][code]

    return app.respond({}, 200, error=False)

@auth.route("/session", methods=["GET", "DELETE"])
def current_session():
    if request.method == "GET":
        session_data = request.session_data.copy()
        session_data["authed"] = request.session.usered

        return app.respond(session_data, 200, error=False)
    elif request.method == "DELETE":
        file_write = app.meower.files.delete_item("usersv0", )
        if not file_write:
            abort(500)

        return app.respond({}, 200, error=False)

@auth.route("/all_sessions", methods=["DELETE"])
def all_sessions():
    if request.method == "DELETE":
        app.meower.files.delete_all("keys", {"u": request.session.user, "type": 1})

        app.meower.commands.abruptLogout(request.session.user, "session_expired")

        return app.respond({}, 200, error=False)

@auth.route("/mfa", methods=["GET", "POST", "DELETE"])
def mfa():
    if request.method == "GET":
        mfa_secret = app.meower.accounts.new_mfa_secret()
        return app.respond({"secret": mfa_secret, "totp_app": "otpauth://totp/Meower: {0}?secret={1}&issuer=Meower".format(request.session.user, mfa_secret)}, 200, error=False)
    elif request.method == "POST":
        if not (("secret" in request.form) and ("code" in request.form)):
            return app.respond({"type": "missingField"}, 400, error=True)
        
        # Extract secret and code for simplicity
        secret = request.form.get("secret")
        code = request.form.get("code")

        # Check for bad datatypes and syntax
        if not ((type(secret) == str) and (type(code) == str)):
            return app.respond({"type": "badDatatype"}, 400, error=True)
        elif (len(secret) != 32) or (len(code) != 6):
            return app.respond({"type": "fieldNotCorrectSize"}, 400, error=True)
        elif app.meower.supporter.checkForBadCharsPost(secret) or app.meower.supporter.checkForBadCharsPost(code):
            return app.respond({"type": "illegalCharacters"}, 400, error=True)
        
        # Check if code matches secret
        if app.meower.accounts.check_mfa(request.session.user, code, custom_secret=secret) != (True, True):
            return app.respond({"type": "mfaCodeInvalid"}, 401, error=True)
        
        # Generate recovery codes
        recovery_codes = []
        for i in range(6):
            tmp_recovery_code = ""
            for i in range(8):
                tmp_recovery_code = tmp_recovery_code+secrets.choice(string.ascii_letters+string.digits)
            recovery_codes.append(tmp_recovery_code.lower())

        # Update userdata
        file_write = app.meower.accounts.update_config(request.session.user, {"mfa_secret": secret, "mfa_recovery": recovery_codes}, forceUpdate=True)
        if not file_write:
            abort(500)

        app.meower.ws.sendPayload(request.session.user, "update_config", "", username=request.session.user)

        return app.respond({"recovery": recovery_codes}, 200, error=False)
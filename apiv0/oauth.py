from flask import Blueprint, request, abort
from flask import current_app as meower
import secrets
import string

oauth = Blueprint("oauth_blueprint", __name__)

"""
@oauth.before_app_request
def before_request():
    # Check for trailing backslashes in the URL
    if request.path.endswith("/"):
        request.path = request.path[:-1]

    # Extract the user's Cloudflare IP address from the request
    if "Cf-Connecting-Ip" in request.headers:
        request.remote_addr = request.headers["Cf-Connecting-Ip"]

    # Check if IP is banned
    if (request.remote_addr in meower.ip_banlist) and (not (request.path in ["/v0", "/v0/status", "/status"] or request.path.startswith("/admin"))):
        return meower.respond({"type": "IPBlocked"}, 403)

    class Session:
        def __init__(self, token):
            file_read, token_data = meower.meower.accounts.get_token(token)
            if file_read:
                self.authed = True
                self.user = token_data["user"]
                self.user_agent = token_data["user_agent"]
                self.oauth_app = token_data["oauth"]["app"]
                self.scopes = token_data["oauth"]["scopes"]
                self.created = token_data["created"]
                self.expires = token_data["expires"]

                file_read, user_data = meower.meower.accounts.get_account(self.user, scopes=self.scopes)
                self.user_data = user_data
            else:
                self.authed = False
                self.user = None
                self.user_agent = None
                self.oauth_app = None
                self.scopes =  None
                self.created = None
                self.expires = None
                self.user_data = None

        def __str__(self):
            return self.user

    # Check whether the client is authenticated
    if "Authorization" in request.headers:
        if len(request.headers.get("Authorization")) <= 100:
            token = request.headers.get("Authorization")
            request.session = Session(token)

    # Exit request if client is not authenticated
    if not (request.session.authed or (request.method == "OPTIONS") or (request.path in ["/", "/v0", "/status", "/v0/status", "/v0/me/login", "/v0/me/create"]) or request.path.startswith("/admin")):
        abort(401)
"""

@oauth.route("/login", methods=["POST"])
def login():
    if not (("username" in request.form) and ("password" in request.form)):
        return meower.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    username = request.form.get("username").strip()
    password = request.form.get("password").strip()

    # Check for bad datatypes and syntax
    if not ((type(username) == str) and (type(password) == str)):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(username) > 20) or (len(password) > 72):
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif meower.meower.supporter.checkForBadCharsUsername(username):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check account flags and password
    file_read, userdata = meower.meower.accounts.get_account(username)
    if not file_read:
        return meower.respond({"type": "accountDoesNotExist"}, 401, error=True)
    elif userdata["flags"]["locked"]:
        return meower.respond({"type": "accountLocked", "expires": userdata["userdata"]["flags"]["locked_until"]-meower.meower.timestamp(6)}, 401, error=True)
    elif userdata["flags"]["dormant"]:
        return meower.respond({"type": "accountDormant"}, 401, error=True)
    elif (meower.meower.accounts.check_password(username, password) != (True, True)):
        return meower.respond({"type": "invalidPassword"}, 401, error=True)
    elif userdata["flags"]["deleted"]:
        return meower.respond({"type": "accountDeleted"}, 401, error=True)
    elif userdata["flags"]["banned"]:
        return meower.respond({"type": "accountBanned", "expires": userdata["userdata"]["flags"]["banned_until"]-meower.meower.timestamp(6)}, 401, error=True)
    
    # Restore account if it's pending deletion
    if userdata["flags"]["pending_deletion"]:
        file_write = meower.meower.accounts.update_config(username, {"flags.delete_after": None}, forceUpdate=True)
        if not file_write:
            abort(500)

    # Generate new token and return to user
    if userdata["userdata"]["mfa_secret"] != None:
        # MFA only token
        token_type = "MFA"
        file_write, token = meower.meower.accounts.create_token(username, expiry=600, scopes=["mfa"])
        if not file_write:
            abort(500)
    else:
        # Full account token
        token_type = "Bearer"
        file_write, token = meower.meower.accounts.create_token(username, expiry=2592000, scopes=["all"])
        if not file_write:
            abort(500)

    return meower.respond({"token": token, "type": token_type}, 200, error=False)

@oauth.route("/login/mfa", methods=["POST"])
def login_mfa():
    if not (("token" in request.form) and ("code" in request.form)):
        return meower.respond({"type": "missingField"}, 400, error=True)
    
    # Extract token and MFA code for simplicity
    token = request.form.get("token")
    code = request.form.get("code")

    # Check for bad datatypes and syntax
    if not ((type(token) == str) and (type(code) == str)):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(token) > 100) or (len(code) > 6):
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

    # Get user from token
    file_read, token_data = meower.meower.accounts.get_token(token)
    if not (file_read or ("mfa" in token_data["scopes"])):
        return meower.respond({"type": "tokenInvalid"}, 401, error=True)
    else:
        user = token_data["user"]

    # Check MFA code
    if meower.meower.accounts.check_mfa(user, code) != (True, True):
        return meower.respond({"type": "mfaInvalid"}, 401, error=True)

    # Delete temporary MFA token
    meower.meower.accounts.delete_token(token)

    # Generate full account token and return to user
    file_write, token = meower.meower.accounts.create_token(user, expiry=2592000, scopes=["all"])
    if not file_write:
        abort(500)
    else:
        return meower.respond({"token": token, "type": "Bearer"}, 200, error=False)

@oauth.route("/create", methods=["POST"])
def create_account():
    if not (("username" in request.form) and ("password" in request.form)):
        return meower.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    username = request.form.get("username").strip()
    password = request.form.get("password").strip()

    # Check for bad datatypes and syntax
    if not ((type(password) == str) and (type(password) == str)):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(username) > 20) or (len(password) > 72):
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif meower.meower.supporter.checkForBadCharsUsername(username):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check if account exists
    if meower.meower.accounts.does_username_exist("usersv0", username):
        return meower.respond({"type": "accountAlreadyExists"}, 401, error=True)

    # Create userdata
    file_write = meower.meower.accounts.create_account(username, password)
    if not file_write:
        abort(500)

    # Generate new token and return to user
    file_write, token = meower.meower.accounts.create_token(username, expiry=2592000, scopes=["all"])
    if file_write:
        return meower.respond({"token": token, "type": "Bearer"}, 200, error=False)
    else:
        abort(500)

@oauth.route("/login_code", methods=["POST"])
def auth_login_code():
    if not ("code" in request.form):
        return meower.respond({"type": "missingField"}, 400, error=True)
    
    # Extract code for simplicity
    code = request.form.get("code")

    # Check for bad datatypes and syntax
    if not (type(code) == str):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif len(code) > 6:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif meower.meower.supporter.checkForBadCharsPost(code):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)
    
    # Check if code exists
    if not (code in meower.meower.cl.statedata["ulist"]["login_codes"]):
        return meower.respond({"type": "codeDoesNotExist"}, 400, error=True)
    
    # Create new token
    file_write, token = meower.meower.accounts.create_token(request.session.user, expiry=2592000, type=1)
    if not file_write:
        abort(500)

    # Send token to client
    meower.meower.ws.sendPayload(meower.meower.cl.statedata["ulist"]["login_codes"][code], "login_code", token)

    # Delete login code
    meower.meower.supporter.modify_client_statedata(meower.meower.cl.statedata["ulist"]["login_codes"][code], "login_code", None)
    del meower.meower.cl.statedata["ulist"]["login_codes"][code]

    return meower.respond({}, 200, error=False)

@oauth.route("/session", methods=["GET", "DELETE"])
def current_session():
    if request.method == "GET":
        session_data = request.session_data.copy()
        session_data["authed"] = request.session.usered

        return meower.respond(session_data, 200, error=False)
    elif request.method == "DELETE":
        file_write = meower.meower.files.delete_item("usersv0", )
        if not file_write:
            abort(500)

        return meower.respond({}, 200, error=False)

@oauth.route("/mfa", methods=["GET", "POST", "DELETE"])
def mfa():
    if request.method == "GET":
        mfa_secret = meower.meower.accounts.new_mfa_secret()
        return meower.respond({"secret": mfa_secret, "totp_app": "otpauth://totp/Meower: {0}?secret={1}&issuer=Meower".format(request.session.user, mfa_secret)}, 200, error=False)
    elif request.method == "POST":
        if not (("secret" in request.form) and ("code" in request.form)):
            return meower.respond({"type": "missingField"}, 400, error=True)
        
        # Extract secret and code for simplicity
        secret = request.form.get("secret")
        code = request.form.get("code")

        # Check for bad datatypes and syntax
        if not ((type(secret) == str) and (type(code) == str)):
            return meower.respond({"type": "badDatatype"}, 400, error=True)
        elif (len(secret) != 32) or (len(code) != 6):
            return meower.respond({"type": "fieldNotCorrectSize"}, 400, error=True)
        
        # Check if code matches secret
        if meower.meower.accounts.check_mfa(request.session.user, code, custom_secret=secret) != (True, True):
            return meower.respond({"type": "mfaCodeInvalid"}, 401, error=True)
        
        # Generate recovery codes
        recovery_codes = []
        for i in range(6):
            tmp_recovery_code = ""
            for i in range(8):
                tmp_recovery_code = tmp_recovery_code+secrets.choice(string.ascii_letters+string.digits)
            recovery_codes.append(tmp_recovery_code.lower())

        # Update userdata
        file_write = meower.meower.accounts.update_config(request.session.user, {"mfa_secret": secret, "mfa_recovery": recovery_codes}, forceUpdate=True)
        if not file_write:
            abort(500)

        meower.meower.ws.sendPayload(request.session.user, "update_config", "", username=request.session.user)

        return meower.respond({"recovery": recovery_codes}, 200, error=False)
    elif request.method == "DELETE":
        if not ("code" in request.form):
            return meower.respond({"type": "missingField"}, 400, error=True)

        # Extract code for simplicity
        code = request.form.get("code")

        # Check for bad datatypes and syntax
        if not (type(code) == str):
            return meower.respond({"type": "badDatatype"}, 400, error=True)
        elif len(code) != 6:
            return meower.respond({"type": "fieldNotCorrectSize"}, 400, error=True)
        
        # Check if code matches secret
        if meower.meower.accounts.check_mfa(request.session.user, code) != (True, True):
            return meower.respond({"type": "mfaCodeInvalid"}, 401, error=True)

        # Update userdata
        file_write = meower.meower.accounts.update_config(request.session.user, {"mfa_secret": None, "mfa_recovery": None}, forceUpdate=True)
        if not file_write:
            abort(500)
        
        meower.meower.ws.sendPayload(request.session.user, "update_config", "", username=request.session.user)

        return meower.respond({}, 200, error=False)
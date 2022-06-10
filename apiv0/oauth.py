from flask import Blueprint, request, abort, render_template
from flask import current_app as meower
import secrets
import string
import bcrypt
import pyotp
import time
import requests
from uuid import uuid4

oauth = Blueprint("oauth_blueprint", __name__, template_folder="templates")

def generate_token(length=32):
    return "{0}.{1}".format(str(secrets.token_urlsafe(length)), float(time.time()))

def create_session(user, oauth_app=None, scopes=[], expiry_time=1800, renewable=True):
    token = {
        "_id": str(uuid4()),
        "user": user,
        "user_agent": request.headers.get("User-Agent"),
        "oauth_app": oauth_app,
        "scopes": scopes,
        "access_token": generate_token(32),
        "access_expiry": int(time.time()) + expiry_time,
        "renew_token": generate_token(128) if renewable else None,
        "renew_expiry": int(time.time()) + 31556952 if renewable else None,
        "previous_renew_tokens": [] if renewable else None,
        "created": int(time.time())
    }
    meower.db["sessions"].insert_one(token)
    return token

def send_email(email, name, subject, body, type="text/plain"):
    if meower.auth_keys is not None:
        status = requests.post("https://email-worker.meower.workers.dev", headers={
            "X-Auth-Token": meower.auth_keys["key"]
        }, json={
            "personalizations": [{
                "to": [{
                    "email": email,
                    "name": name
                }],
            }],
            "from": {
                "email": "no-reply@meower.org",
                "name": "Meower"
            },
            "subject": subject,
            "content": [{
                "type": type,
                "value": body
            }]
        })
    else:
        meower.log("Email worker not configured. Skipping email.")

def password_reset_email(email, user):
    # Get userdata
    userdata = meower.db["usersv0"].find_one({"_id": user})

    # Create token
    token = generate_token(32)
    create_session(user, None, ["password_reset"], expiry_time=900, renewable=False)

    # Render and send email
    email_body = render_template("email/recovery.html", username=userdata["username"], token=token)
    send_email(email, userdata["username"], "Meowy says: Oh no, I can't get in!", email_body, type="text/html")

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
            if token is not None:
                token_data = meower.db.sessions.find_one({"access_token": token, "access_expiry": {"$gt": int(time.time())}})
            
            if token_data is not None:
                self.json = token_data
                self.authed = True
                self.id = token_data["_id"]
                self.user = token_data["user"]
                self.user_agent = token_data["user_agent"]
                self.oauth_app = token_data["oauth_app"]
                self.scopes = token_data["scopes"]
                self.expires = token_data["access_expiry"]
                self.renew = token_data["renew_token"]
                self.created = token_data["created"]
                self.userdata = meower.db.users.find_one({"_id": self.user})
            else:
                self.json = None
                self.authed = False
                self.id = None
                self.user = None
                self.user_agent = None
                self.oauth_app = None
                self.scopes =  None
                self.expires = None
                self.renew = None
                self.created = None
                self.userdata = None

        def __str__(self):
            return self.user

        def delete(self):
            if self.authed:
                meower.db.sessions.delete_one({"_id": self.id})
                return True
            else:
                return False

    # Check whether the client is authenticated
    if len(str(request.headers.get("Authorization"))) <= 100:
        request.session = Session(str(request.headers.get("Authorization")).replace("Bearer ", ""))
    else:
        return meower.respond({"type": "tokenTooLarge"}, 400, error=True)

    # Exit request if client is not authenticated
    if not (request.session.authed or (request.method == "OPTIONS") or (request.path in ["/", "/v0", "/status", "/v0/status", "/v0/socket", "/v0/oauth/login", "/v0/oauth/create", "/v0/oauth/session/refresh"]) or request.path.startswith("/admin")):
        abort(401)

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
    elif meower.check_for_bad_chars_username(username):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check account flags and password
    userdata = meower.db["usersv0"].find_one({"lower_username": username.lower()})
    if userdata is None:
        return meower.respond({"type": "accountDoesNotExist"}, 401, error=True)
    elif (userdata["security"]["locked_until"] > int(time.time())) or (userdata["security"]["locked_until"] == -1):
        return meower.respond({"type": "accountLocked", "expires": userdata["security"]["locked_until"]}, 401, error=True)
    elif userdata["security"]["dormant"]:
        return meower.respond({"type": "accountDormant"}, 401, error=True)
    elif not bcrypt.checkpw(bytes(password, "utf-8"), bytes(userdata["security"]["password"], "utf-8")):
        return meower.respond({"type": "invalidPassword"}, 401, error=True)
    elif userdata["security"]["deleted"]:
        return meower.respond({"type": "accountDeleted"}, 401, error=True)
    elif (userdata["security"]["banned_until"] > int(time.time())) or (userdata["security"]["banned_until"] == -1):
        return meower.respond({"type": "accountBanned", "expires": userdata["security"]["banned_until"]}, 401, error=True)
    
    # Restore account if it's pending deletion
    if userdata["security"]["delete_after"] is not None:
        meower.db["usersv0"].update_one({"_id": userdata["_id"]}, {"$set": {"security.delete_after": None}})

    # Generate new token and return to user
    if userdata["security"]["mfa_secret"] is not None:
        # MFA only token
        token_data = create_session(userdata["_id"], scopes=["mfa"], expiry_time=900, renewable=False)
        return meower.respond({"session": token_data, "user": None, "requires_mfa": True}, 200, error=False)
    else:
        # Full account token
        token_data = create_session(userdata["_id"], scopes=["all"])
        del userdata["security"]
        return meower.respond({"session": token_data, "user": userdata, "requires_mfa": False}, 200, error=False)

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
    token_data = meower.db["sessions"].find_one({"token": token})
    if token_data is None:
        return meower.respond({"type": "tokenInvalid"}, 401, error=True)
    elif not ("mfa" in token_data["oauth"]["scopes"]):
        return meower.respond({"type": "tokenInvalid"}, 401, error=True)
    elif token_data["expires"] < int(time.time()):
        return meower.respond({"type": "tokenInvalid"}, 401, error=True)
    else:
        user = token_data["user"]
        userdata = meower.db["usersv0"].find_one({"_id": user})
        if userdata is None:
            return meower.respond({"type": "tokenInvalid"}, 401, error=True)
        else:
            del userdata["security"]

    # Check MFA code
    if pyotp.TOTP(userdata["security"]["mfa_secret"]).now() != code:
        return meower.respond({"type": "mfaInvalid"}, 401, error=True)

    # Delete temporary MFA token
    meower.db["usersv0"].delete_one({"_id": token_data["_id"]})

    # Generate full account token and return to user
    token_data = create_session(userdata["_id"], scopes=["all"])
    return meower.respond({"session": token_data, "user": userdata, "requires_mfa": False}, 200, error=False)

@oauth.route("/login/reset-password", methods=["POST"])
def reset_password():
    if not (("username" in request.form) and ("email" in request.form)):
        return meower.respond({"type": "missingField"}, 400, error=True)
    
    # Extract username and email for simplicity
    username = request.form.get("username").strip()
    email = request.form.get("email").strip()

    # Check for bad datatypes and syntax
    if not ((type(username) == str) and (type(email) == str)):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(username) > 20) or (len(email) > 100):
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif meower.check_for_bad_chars_username(username):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)
    
    # Check account exists and email is valid
    userdata = meower.db["usersv0"].find_one({"lower_username": username.lower()})
    if userdata is None:
        return meower.respond({"type": "accountDoesNotExist"}, 401, error=True)
    elif userdata["security"]["email"] is None:
        return meower.respond({"type": "invalidEmail"}, 401, error=True)
    elif not bcrypt.checkpw(bytes(email, "utf-8"), bytes(userdata["security"]["email"], "utf-8")):
        return meower.respond({"type": "invalidEmail"}, 401, error=True)

    password_reset_email(email, userdata["_id"])
    return meower.respond({}, 200, error=False)

@oauth.route("/register", methods=["POST"])
def register():
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
    elif meower.check_for_bad_chars_username(username):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check if account exists
    if meower.db["usersv0"].find_one({"lower_username": username.lower()}) is not None:
        return meower.respond({"type": "accountAlreadyExists"}, 401, error=True)

    # Create userdata
    userdata = {
        "_id": str(uuid4()),
        "username": username,
        "lower_username": username.lower(),
        "state": 0,
        "created": int(time.time()),
        "config": {
            "unread_inbox": False,
            "theme": "orange",
            "mode": True,
            "sound_effects": True,
            "background_music": {
                "enabled": True,
                "type": "default",
                "data": 2
            }
        },
        "profile": {
            "avatar": {
                "type": "default",
                "data": 1
            },
            "bio": "",
            "status": 1,
            "last_seen": 0
        },
        "security": {
            "email": None,
            "password": bcrypt.hashpw(bytes(password, "utf-8"), bcrypt.gensalt(12)).decode(),
            "mfa_secret": None,
            "mfa_recovery": None,
            "last_ip": None,
            "dormant": False,
            "locked_until": 0,
            "suspended_until": 0,
            "banned_until": 0,
            "delete_after": None,
            "deleted": False
        },
        "ratelimits": {
            "authentication": 0,
            "change_username": 0,
            "change_password": 0,
            "email_verification": 0,
            "reset_password": 0,
            "data_export": 0
        }
    }
    meower.db["usersv0"].insert_one(userdata)

    # Generate new token and return to user
    token = create_session(userdata["_id"], scopes=["all"])
    del userdata["security"]
    return meower.respond({"session": token, "user": userdata, "requires_mfa": False}, 200, error=False)

@oauth.route("/login-code", methods=["POST"])
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
    elif meower.supporter.checkForBadCharsPost(code):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)
    
    # Check if code exists
    if not (code in meower.cl.statedata["ulist"]["login_codes"]):
        return meower.respond({"type": "codeDoesNotExist"}, 400, error=True)
    
    # Create new token
    file_write, token = meower.accounts.create_token(request.session.user, expiry=2592000, type=1)
    if not file_write:
        abort(500)

    # Send token to client
    meower.ws.sendPayload(meower.cl.statedata["ulist"]["login_codes"][code], "login_code", token)

    # Delete login code
    meower.supporter.modify_client_statedata(meower.cl.statedata["ulist"]["login_codes"][code], "login_code", None)
    del meower.cl.statedata["ulist"]["login_codes"][code]

    return meower.respond({}, 200, error=False)

@oauth.route("/session", methods=["GET", "DELETE"])
def current_session():
    if request.method == "GET":
        payload = {
            "authed": request.session.authed,
            "user": request.session.user,
            "oauth_app": request.session.oauth_app,
            "scopes": request.session.scopes,
            "expires": request.session.expires
        }

        return meower.respond(payload, 200, error=False)
    elif request.method == "DELETE":
        file_write = request.session.delete()
        return meower.respond({}, (200 if file_write else 500), error=file_write)

@oauth.route("/session/refresh", methods=["POST"])
def refresh_session():
    if not ("token" in request.form):
        return meower.respond({"type": "missingField"}, 400, error=True)
    
    # Extract token for simplicity
    token = request.form.get("token")

    # Check for bad datatypes and syntax
    if not (type(token) == str):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif len(token) <= 100:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

    # Check for token reuse
    meower.db["sessions"].delete_many({"previous_renew_tokens": {"$all": [token]}})

    # Get token data
    token_data = meower.db["sessions"].find_one({"renew_token": token, "renew_expiry": {"$gt": int(time.time())}})
    if token_data is None:
        return meower.respond({"type": "tokenDoesNotExist"}, 400, error=True)
    else:
        # Renew token
        token_data["access_token"] = generate_token(32)
        token_data["access_expiry"] = int(time.time()) + 1800
        token_data["renew_token"] = generate_token(128)
        token_data["previous_renew_tokens"].append(token)
        meower.db["sessions"].update_one({"_id": token_data["_id"]}, {"$set": token_data})
        userdata = meower.db["usersv0"].find_one({"_id": token_data["user"]})
        return meower.respond({"session": token, "user": userdata, "requires_mfa": False}, 200, error=False)

@oauth.route("/mfa", methods=["GET", "POST", "DELETE"])
def mfa():
    if request.method == "GET":
        mfa_secret = meower.accounts.new_mfa_secret()
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
        if meower.accounts.check_mfa(request.session.user, code, custom_secret=secret) != (True, True):
            return meower.respond({"type": "mfaCodeInvalid"}, 401, error=True)
        
        # Generate recovery codes
        recovery_codes = []
        for i in range(6):
            tmp_recovery_code = ""
            for i in range(8):
                tmp_recovery_code = tmp_recovery_code+secrets.choice(string.ascii_letters+string.digits)
            recovery_codes.append(tmp_recovery_code.lower())

        # Update userdata
        file_write = meower.accounts.update_config(request.session.user, {"mfa_secret": secret, "mfa_recovery": recovery_codes}, forceUpdate=True)
        if not file_write:
            abort(500)

        meower.ws.sendPayload(request.session.user, "update_config", "", username=request.session.user)

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
        if meower.accounts.check_mfa(request.session.user, code) != (True, True):
            return meower.respond({"type": "mfaCodeInvalid"}, 401, error=True)

        # Update userdata
        file_write = meower.accounts.update_config(request.session.user, {"mfa_secret": None, "mfa_recovery": None}, forceUpdate=True)
        if not file_write:
            abort(500)
        
        meower.ws.sendPayload(request.session.user, "update_config", "", username=request.session.user)

        return meower.respond({}, 200, error=False)
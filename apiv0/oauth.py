from jinja2 import Template
from flask import Blueprint, request, abort, render_template
from flask import current_app as meower
from httplib2 import Authentication
from passlib.hash import scrypt, bcrypt
from hashlib import sha256
import secrets
import string
import pyotp
import time
import requests
from uuid import uuid4
import json
import string

oauth = Blueprint("oauth_blueprint", __name__)

def generate_token(length):
    return "{0}.{1}".format(str(secrets.token_urlsafe(length)), float(time.time()))

def create_session(type, user, token, expires=None, action=None, app=None, scopes=None):
    # Base session data
    session_data = {
        "_id": str(uuid4()),
        "type": type,
        "user": user,
        "user_agent": (request.headers.get("User-Agent") if "User-Agent" in request.headers else None),
        "token": token,
        "expires": None,
        "created": time.time(),
        "revoked": False
    }
    
    # Add specific data for each type
    if type == 0:
        session_data["action"] = action
    elif type == 1:
        session_data["verified"] = False
    elif type == 4:
        session_data["app"] = app
        session_data["scopes"] = scopes
        session_data["refresh_token"] = generate_token(128)
        session_data["refresh_expires"] = time.time() + 31556952
        session_data["previous_refresh_tokens"] = []

    # Add any missing data
    for item in ["_id", "type", "user", "action", "app", "scopes", "refresh_token", "refresh_expires", "previous_refresh_tokens", "user_agent", "token", "expires", "created", "revoked"]:
        if item not in session_data:
            session_data[item] = None

    # Set expiration time
    if expires is not None:
        session_data["expires"] = time.time() + expires
    else:
        session_data["expires"] = time.time() + {1: 300, 2: 300, 3: 31556952, 4: 1800}[session_data["type"]]

    # Add session to database and return session data
    meower.db["sessions"].insert_one(session_data)
    return session_data

def foundation_session(user):
    # Create session
    session = create_session(3, user, generate_token(64))
    del session["previous_refresh_tokens"]

    # Get user data
    userdata = meower.db["usersv0"].find_one({"_id": user})
    # Restore account if it's pending deletion
    if userdata["security"]["delete_after"] is not None:
        meower.db["usersv0"].update_one({"_id": userdata["_id"]}, {"$set": {"security.delete_after": None}})
    del userdata["security"]

    # Return session data
    return {"session": session, "user": userdata, "requires_mfa": False, "mfa_options": None}

@oauth.before_app_request
def before_request():
    # Check for trailing backslashes in the URL
    if request.path.endswith("/"):
        request.path = request.path[:-1]

    # Make sure request method is upper case
    request.method = str(request.method).upper()

    # Extract the user's Cloudflare IP address from the request
    if "Cf-Connecting-Ip" in request.headers:
        request.remote_addr = request.headers["Cf-Connecting-Ip"]

    # Check if IP is banned
    if (request.remote_addr in meower.ip_banlist) and (not (request.path in ["/v0", "/v0/status", "/status"] or request.path.startswith("/admin"))):
        return meower.respond({"type": "IPBlocked"}, 403)

    class Session:
        def __init__(self, token):
            # Get session data from database
            token_data = meower.db.sessions.find_one({"token": token})
            
            # Check if session is valid
            self.authed = False
            try:
                if (token_data is not None) and (token_data["type"] == 3 or token_data["type"] == 4):
                    self.json = token_data
                    for key, value in token_data.items():
                        setattr(self, key, value)
                    if (not ((self.expires < time.time()) or self.revoked)) or (self.expires == None):
                        self.authed = True
            except:
                pass

        def renew(self):
            # Renew session
            meower.db.sessions.update_one({"_id": self._id}, {"$set": {"expires": time.time() + self.expires}})
            self.expires = time.time() + self.expires

        def revoke(self):
            # Revoke session
            self.revoked = True
            meower.db.sessions.update_one({"_id": self._id}, {"$set": {"revoked": True}})
        
        def delete(self):
            # Delete session
            meower.db.sessions.delete_one({"_id": self._id})

    # Check whether the client is authenticated
    if ("Authorization" in request.headers) or (len(str(request.headers.get("Authorization"))) <= 136):
        request.session = Session(str(request.headers.get("Authorization")).replace("Bearer ", "").strip())

    # Exit request if client is not authenticated
    if not (request.session.authed or (request.method == "OPTIONS") or (request.path in ["/", "/v0", "/status", "/v0/status", "/v0/socket", "/v0/oauth/login", "/v0/oauth/auth-methods", "/v0/oauth/create", "/v0/oauth/login/email", "/v0/oauth/login/device", "/v0/oauth/login/mfa", "/v0/oauth/session/refresh"]) or request.path.startswith("/admin")):
        abort(401)

@oauth.route("/create", methods=["POST"])
def create_account():
    # Check for account creation block
    if meower.db["netlog"].find_one({"_id": request.remote_addr, "creation_blocked": True}) is not None:
        return meower.respond({"type": "accountCreationBlocked"}, 403, error=True)

    # Check for required data
    if not (("username" in request.json) and ("password" in request.json)):
        return meower.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    username = request.json["username"].strip()
    password = request.json["password"].strip()

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
        "deleted": False,
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
            "authentication_methods": [
                {
                    "id": str(uuid4()),
                    "type": "password",
                    "mfa_method": False,
                    "hash_type": "scrypt",
                    "password_hash": scrypt.hash(sha256(password.encode()).hexdigest())
                }
            ],
            "default_method": 0,
            "last_changed_username": 0,
            "last_requested_data": 0,
            "delete_after": None,
            "suspended_until": None,
            "banned": False
        }
    }
    if "email" in request.json:
        userdata["security"]["authentication_methods"].append({
            "id": str(uuid4()),
            "type": "email",
            "mfa_method": False,
            "verified": False,
            "encrypted_email": "",
            "encryption_id": ""
        })
    meower.db["usersv0"].insert_one(userdata)

    # Generate new session and return to user
    session = create_session(3, userdata["_id"], generate_token(64))
    del userdata["security"]
    return meower.respond({"session": session, "user": userdata, "requires_mfa": False}, 200, error=False)

@oauth.route("/auth-methods", methods=["GET"])
def get_auth_methods():
    # Check for required data
    if not ("username" in request.json):
        return meower.respond({"type": "missingField"}, 400, error=True)

    # Extract username for simplicity
    username = request.json["username"].strip()

    # Check for bad datatypes and syntax
    if not (type(username) == str):
        return meower.respond({"type": "accountDoesNotExist"}, 400, error=True)
    elif len(username) > 20:
        return meower.respond({"type": "accountDoesNotExist"}, 400, error=True)
    elif meower.check_for_bad_chars_username(username):
        return meower.respond({"type": "accountDoesNotExist"}, 400, error=True)

    # Make sure account exists and check if it is able to be accessed
    userdata = meower.db["usersv0"].find_one({"lower_username": username.lower()})
    if userdata is None:
        # Account does not exist
        return meower.respond({"type": "accountDoesNotExist"}, 401, error=True)
    elif len(userdata["security"]["authentication_methods"]) == 0:
        # Account doesn't have any authentication methods
        return meower.respond({"type": "noAuthenticationMethods"}, 401, error=True)

    # Give authentication methods
    methods_payload = []
    for method in userdata["security"]["authentication_methods"]:
        if not (method["type"] in methods_payload):
            methods_payload.append(method["type"])
    return meower.respond({"methods": methods_payload, "default": userdata["security"]["default_method"]}, 200, error=False)

@oauth.route("/login", methods=["POST"])
def login():
    # Check for required data
    if not (("username" in request.json) and ("auth_method" in request.json)):
        return meower.respond({"type": "missingField"}, 400, error=True)

    # Extract username and password for simplicity
    username = request.json["username"].strip()
    auth_method = request.json["auth_method"].strip().lower()

    # Check for bad datatypes and syntax
    if not ((type(username) == str) and (type(auth_method) == str)):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif len(username) > 20:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif meower.check_for_bad_chars_username(username):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)

    # Make sure the account exists and check account flags
    userdata = meower.db["usersv0"].find_one({"lower_username": username.lower()})
    if userdata is None:
        # Account does not exist
        return meower.respond({"type": "accountDoesNotExist"}, 401, error=True)
    elif userdata["deleted"]:
        # Account is deleted
        return meower.respond({"type": "accountDeleted"}, 401, error=True)
    elif userdata["security"]["banned"]:
        # Account is banned
        return meower.respond({"type": "accountBanned"}, 401, error=True)
    elif len(userdata["security"]["authentication_methods"]) == 0:
        # Account doesn't have any authentication methods
        return meower.respond({"type": "noAuthenticationMethods"}, 401, error=True)
    
    # Check for valid authentication
    valid = False
    if auth_method == "password":
        if not ("password" in request.form):
            return meower.respond({"type": "missingField"}, 400, error=True)
        attempted_password = sha256(request.json["password"].strip().encode()).hexdigest()
        for method in userdata["security"]["authentication_methods"]:
            if method["type"] != "password":
                continue
            elif (method["hash_type"] == "scrypt") and scrypt.verify(attempted_password, method["password_hash"]):
                valid = True
                break
            elif (method["hash_type"] == "bcrypt") and bcrypt.verify(str(request.json["password"]), method["password_hash"]):
                # Legacy support for Meower Scratch 4.7-5.6 -- updates to scrypt on first login
                meower.db["usersv0"].update_one({"_id": userdata["_id"], "security.authentication_methods": {"$elemMatch": {"hash_type": "bcrypt"}}}, {"$set": {"security.authentication_methods.$.hash_type": "scrypt", "security.authentication_methods.$.password_hash": scrypt.hash(attempted_password)}})
                valid = True
                break
            elif (method["hash_type"] == "sha256") and (method["password_hash"] == sha256(attempted_password.encode()).hexdigest()):
                # Legacy support for Meower Scratch 4.5-4.6 -- updates to scrypt on first login
                meower.db["usersv0"].update_one({"_id": userdata["_id"], "security.authentication_methods": {"$elemMatch": {"hash_type": "sha256"}}}, {"$set": {"security.authentication_methods.$.hash_type": "scrypt", "security.authentication_methods.$.password_hash": scrypt.hash(attempted_password)}})
                valid = True
                break
        if valid:
            return meower.respond(foundation_session(userdata["_id"]), 200, error=False)
        else:
            return meower.respond({"type": "invalidCredentials"}, 401, error=True)
    elif auth_method == "email":
        if meower.check_for_spam("email_login", userdata["_id"], 60):
            return meower.respond({"type": "tooManyRequests"}, 429, error=True)
        new_code = str("".join(secrets.choice(string.ascii_letters + string.digits) for i in range(8))).upper()
        create_session(0, userdata["_id"], new_code, expires=600, action="login")
        with open("apiv0/email_templates/verification_code.html", "r") as f:
            email_template = f.read()
        meower.send_email([userdata["_id"]], "Login Code", Template(email_template).render({"username": userdata["username"], "code": new_code}), type="text/html")
        return meower.respond({}, 200, error=False)
    elif auth_method == "device":
        new_code = str("".join(secrets.choice(string.ascii_letters + string.digits) for i in range(8))).upper()
        session = create_session(1, userdata["_id"], new_code, expires=300)
        del session["previous_refresh_tokens"]
        minimal_userdata = {}
        for key in ["username", "lower_username", "state", "deleted", "created"]:
            minimal_userdata[key] = userdata[key]
        return meower.respond({"session": session, "user": minimal_userdata, "requires_mfa": False, "mfa_options": None}, 200, error=False)
    else:
        return meower.respond({"type": "unknownMethod"}, 400, error=True)

@oauth.route("/login/email", methods=["POST"])
def login_email():
    # Check for required data
    if not (("username" in request.json) and ("code" in request.json)):
        return meower.respond({"type": "missingField"}, 400, error=True)

    # Extract username and given code for simplicity
    username = request.json["username"].strip().lower()
    code = request.json["code"].strip().upper()

    # Check for bad datatypes and syntax
    if not ((type(username) == str) and (type(code) == str)):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(username) > 20) or (len(code) > 8):
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif meower.check_for_bad_chars_username(username):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)

    # Get userdata from database
    userdata = meower.db["usersv0"].find_one({"lower_username": username})

    # Get session data from database
    session_data = meower.db["sessions"].find_one({"token": code})
    if (session_data is None) or (session_data["type"] != 0) or (session_data["user"] != userdata["_id"]) or (session_data["expires"] < time.time()) or session_data["revoked"]:
        return meower.respond({"type": "invalidCredentials"}, 401, error=True)
    else:
        # Delete session
        meower.db["sessions"].delete_one({"_id": session_data["_id"]})
    
        # Full account session
        return meower.respond(foundation_session(userdata["_id"]), 200, error=False)

@oauth.route("/login/device", methods=["GET"])
def login_device():
    # Check whether the client is authenticated
    if ("Authorization" in request.headers) or (len(str(request.headers.get("Authorization"))) <= 136):
        request.session = str(request.headers.get("Authorization").replace("Bearer ", "")).strip()

    # Get session data
    session = meower.db["sessions"].find_one({"token": request.session})

    if (session is None) or (session["type"] != 1) or (session["expires"] < time.time()) or (not session["verified"]) or session["revoked"]:
        # Invalid session or session has not been verified
        abort(401)
    else:
        # Delete session
        meower.db["sessions"].delete_one({"_id": session["user"]})
    
        # Full account session
        return meower.respond(foundation_session(session["user"]), 200, error=False)

@oauth.route("/session", methods=["GET", "DELETE"])
def current_session():
    if request.method == "GET":
        # Get session data from database
        session = request.session.json.copy()
        del session["previous_refresh_tokens"]

        # Get user data from database
        userdata = meower.db["usersv0"].find_one({"_id": session["user"]})
        del userdata["security"]

        # Return session data
        return meower.respond({"session": session, "user": userdata, "foundation_session": (session["type"] == 3), "oauth_session": (session["type"] == 4)}, 200, error=False)
    elif request.method == "DELETE":
        request.session.delete()
        return meower.respond({}, 200, error=False)

""" \/ All this stuff needs to be updated \/
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
    token_data = meower.db["sessions"].find_one({"access_token": token})
    if token_data is None:
        return meower.respond({"type": "tokenInvalid"}, 401, error=True)
    elif not ("mfa" in token_data["scopes"]):
        return meower.respond({"type": "tokenInvalid"}, 401, error=True)
    elif token_data["access_expiry"] < int(time.time()):
        return meower.respond({"type": "tokenInvalid"}, 401, error=True)
    else:
        user = token_data["user"]
        userdata = meower.db["usersv0"].find_one({"_id": user})
        if userdata is None:
            return meower.respond({"type": "tokenInvalid"}, 401, error=True)

    # Check MFA code
    if not pyotp.TOTP(userdata["security"]["mfa_secret"]).verify(code):
        return meower.respond({"type": "mfaInvalid"}, 401, error=True)

    # Delete temporary MFA session
    meower.db["sessions"].delete_one({"_id": token_data["_id"]})

    # Generate full account session and return to user
    session = create_session(0, userdata["_id"], action="foundation", single_use=False, expiry_time=5260000)
    del userdata["security"]
    return meower.respond({"session": session, "user": userdata, "requires_mfa": False}, 200, error=False)

@oauth.route("/login-code", methods=["POST"])
def auth_login_code():
    if not ("code" in request.form):
        return meower.respond({"type": "missingField"}, 400, error=True)
    
    # Extract code for simplicity
    code = request.form.get("code")

    # Check for bad datatypes and syntax
    if not (type(code) == str):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif len(code) > 16:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
    
    # Check if code exists
    if not (code in meower.sock_login_codes):
        return meower.respond({"type": "codeDoesNotExist"}, 400, error=True)
    
    # Create new session
    session = create_session(request.session.user, scopes=["all"])

    # Send session to client
    meower.sock_login_codes[code].client.send(json.dumps({"cmd": "login_code", "val": session}))

    # Delete login code
    del meower.sock_login_codes[code]

    return meower.respond({}, 200, error=False)

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
        del userdata["security"]
        return meower.respond({"session": token_data, "user": userdata, "requires_mfa": False}, 200, error=False)

@oauth.route("/mfa", methods=["GET", "POST", "DELETE"])
def mfa():
    if request.method == "GET":
        mfa_secret = str(pyotp.random_base32())
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
        if not pyotp.TOTP(secret).verify(code):
            return meower.respond({"type": "mfaCodeInvalid"}, 401, error=True)
        
        # Generate recovery codes
        recovery_codes = []
        for i in range(6):
            tmp_recovery_code = ""
            for i in range(8):
                tmp_recovery_code = tmp_recovery_code+secrets.choice(string.ascii_letters+string.digits)
            recovery_codes.append(tmp_recovery_code.lower())

        # Update userdata
        meower.db["usersv0"].update_one({"_id": request.session.user}, {"$set": {"security.mfa_secret": secret, "security.mfa_recovery": recovery_codes}})

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
        userdata = meower.db["usersv0"].find_one({"_id": request.session.user})
        if not pyotp.TOTP(userdata["security"]["mfa_secret"]).verify(code):
            return meower.respond({"type": "mfaCodeInvalid"}, 401, error=True)

        # Update userdata
        meower.db["usersv0"].update_one({"_id": request.session.user}, {"$set": {"security.mfa_secret": None, "security.mfa_recovery": None}})
        
        meower.ws.sendPayload(request.session.user, "update_config", "", username=request.session.user)

        return meower.respond({}, 200, error=False)
"""
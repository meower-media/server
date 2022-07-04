from jinja2 import Template
from flask import Blueprint, request, abort
from flask import current_app as meower
from passlib.hash import scrypt, bcrypt
from hashlib import sha256
import secrets
import string
import pyotp
import time
from uuid import uuid4
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
    elif type == 5:
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
    return {"session": session, "user": userdata, "requires_totp": False}

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
                if (token_data is not None) and (token_data["type"] == 3 or token_data["type"] == 5):
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
        if request.session.authed:
            request.user = request.session.user
        else:
            request.user = None

    # Exit request if client is not authenticated
    if not (request.session.authed or (request.method == "OPTIONS") or (request.path in ["/", "/v0", "/status", "/v0/status", "/v0/socket", "/v0/oauth/login", "/v0/oauth/auth-methods", "/v0/oauth/create", "/v0/oauth/login/totp", "/v0/oauth/login/email", "/v0/oauth/login/device", "/v0/oauth/session/refresh"]) or request.path.startswith("/admin")):
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
            "sfx": True,
            "bgm": {
                "enabled": True,
                "type": "default",
                "data": 2
            }
        },
        "profile": {
            "pfp": {
                "type": "default",
                "data": 1
            },
            "bio": "",
            "status": 1,
            "last_seen": int(time.time())
        },
        "security": {
            "authentication_methods": [
                {
                    "id": str(uuid4()),
                    "type": "password",
                    "hash_type": "scrypt",
                    "password_hash": scrypt.hash(sha256(password.encode()).hexdigest())
                }
            ],
            "default_method": 0,
            "totp": None,
            "oauth": {
                "authorized": [],
                "scopes": {}
            },
            "username_history": [
                {
                    "username": username,
                    "timestamp": int(time.time()),
                    "changed_by_admin": False
                }
            ],
            "moderation_history": [],
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
            "verified": False,
            "encrypted_email": "",
            "encryption_id": ""
        })
    meower.db["usersv0"].insert_one(userdata)

    # Generate new session and return to user
    session = create_session(3, userdata["_id"], generate_token(64))
    del userdata["security"]
    return meower.respond({"session": session, "user": userdata, "requires_totp": False}, 200, error=False)

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
        if not ("password" in request.json):
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
            # Return session
            if userdata["security"]["totp"] is not None:
                session = create_session(2, userdata["_id"], generate_token(64), expires=300)
                del session["previous_refresh_tokens"]
                minimal_userdata = {}
                for key in ["username", "lower_username", "state", "deleted", "created"]:
                    minimal_userdata[key] = userdata[key]
                return meower.respond({"session": session, "user": minimal_userdata, "requires_totp": True}, 200, error=False)
            else:
                return meower.respond(foundation_session(userdata["_id"]), 200, error=False)
        else:
            # Invalid password
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
        return meower.respond({"session": session, "user": minimal_userdata, "requires_totp": False}, 200, error=False)
    else:
        return meower.respond({"type": "unknownMethod"}, 400, error=True)

@oauth.route("/login/totp", methods=["POST"])
def login_totp():
    # Check whether the client is authenticated
    if ("Authorization" in request.headers) or (len(str(request.headers.get("Authorization"))) <= 136):
        token = str(request.headers.get("Authorization").replace("Bearer ", "")).strip()

    # Get session data
    session = meower.db["sessions"].find_one({"token": token})

    # Check if the session is invalid
    if (session is None) or (session["type"] != 2) or (session["expires"] < time.time()) or session["revoked"]:
        abort(401)
    else:
        # Check for required data
        if not ("code" in request.json):
            return meower.respond({"type": "missingField"}, 400, error=True)
        
        # Get user data from database
        userdata = meower.db["usersv0"].find_one({"_id": session["user"]})
  
        # Check for valid authentication
        if (userdata["security"]["totp"] is None) or pyotp.TOTP(userdata["security"]["totp"]).verify(request.json["code"]):
            # Delete session
            meower.db["sessions"].delete_one({"_id": session["_id"]})
        
            # Full account session
            return meower.respond(foundation_session(session["user"]), 200, error=False)
        else:
            # Invalid TOTP code
            return meower.respond({"type": "invalidCredentials"}, 401, error=True)

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

    # Check if the session is invalid or hasn't been verified yet
    if (session is None) or (session["type"] != 1) or (session["expires"] < time.time()) or (not session["verified"]) or session["revoked"]:
        abort(401)
    else:
        # Delete session
        meower.db["sessions"].delete_one({"_id": session["_id"]})
    
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
        return meower.respond({"session": session, "user": userdata, "foundation_session": (session["type"] == 3), "oauth_session": (session["type"] == 5)}, 200, error=False)
    elif request.method == "DELETE":
        # Delete session
        request.session.delete()
        return meower.respond({}, 200, error=False)

@oauth.route("/session/refresh", methods=["POST"])
def refresh_session():
    # Check whether the client is authenticated
    if ("Authorization" in request.headers) or (len(str(request.headers.get("Authorization"))) <= 136):
        request.session = str(request.headers.get("Authorization").replace("Bearer ", "")).strip()

    # Check for bad datatypes and syntax
    if not (type(request.session) == str):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif len(request.session) <= 100:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

    # Check for token reuse
    meower.db["sessions"].delete_many({"previous_renew_tokens": {"$all": [request.session]}})

    # Get token data
    session_data = meower.db["sessions"].find_one({"refresh_token": request.session})
    if (session_data is None) or (session_data["type"] != 5) or (session_data["refresh_expires"] < time.time()) or session_data["revoked"]:
        return meower.respond({"type": "tokenDoesNotExist"}, 400, error=True)
    else:
        # Refresh token
        session_data["token"] = generate_token(64)
        session_data["expires"] = time.time() + 1800
        session_data["refresh_token"] = generate_token(128)
        session_data["previous_refresh_tokens"].append(request.session)
        meower.db["sessions"].update_one({"_id": session_data["_id"]}, {"$set": session_data})
        userdata = meower.db["usersv0"].find_one({"_id": session_data["user"]})
        del userdata["security"]
        return meower.respond({"session": session_data, "user": userdata, "requires_totp": False}, 200, error=False)

@oauth.route("/authorize/device", methods=["POST"])
def authorize_device():
    # Check for required data
    if not ("code" in request.json):
        return meower.respond({"type": "missingField"}, 400, error=True)

    # Extract code for simplicity
    code = request.json["code"].strip().upper()

    # Check for bad datatypes and syntax
    if not (type(code) == str):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif len(code) > 8:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

    # Get session data
    session = meower.db["sessions"].find_one({"token": code})

    # Check if the session is invalid
    if (session is None) or (session["type"] != 1) or (session["expires"] < time.time()) or (session["user"] != request.session.user) or session["verified"] or session["revoked"]:
        return meower.respond({"type": "codeDoesNotExist"}, 400, error=True)
    else:
        # Verify session
        meower.db["sessions"].update_one({"_id": session["_id"]}, {"$set": {"verified": True}})
        return meower.respond({}, 200, error=False)

@oauth.route("/authorize/app", methods=["GET", "POST"])
def authorize_app():
    # Check for required data
    if not (("app" in request.json) and ("scopes" in request.json) and ("redirect_uri" in request.json)):
        return meower.respond({"type": "missingField"}, 400, error=True)
 
    # Extract app ID and scopes for simplicity
    app_id = request.json["app"].strip()
    scopes = request.json["scopes"].strip().split(" ")
    redirect_uri = request.json["redirect_uri"].strip()

    # Check for bad datatypes and syntax
    if not ((type(app_id) == str) or (type(scopes) == list)):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif len(app_id) > 32:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
    elif len(scopes) > 32:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

    # Get app data
    app_data = meower.db["oauth"].find_one({"_id": app_id})
    # Check if the app exists
    if app_data is None:
        return meower.respond({"type": "appDoesNotExist"}, 400, error=True)

    # Get user data
    userdata = meower.db["usersv0"].find_one({"_id": request.session.user})

    if request.method == "GET":
        # Return app information
        payload = app_data.copy()
        del payload["bans"]
        del payload["allowed_redirects"]
        del payload["secret"]
        payload["authorized"] = ((app_id in userdata["security"]["oauth"]["authorized"]) and (userdata["security"]["oauth"]["scopes"][app_id] == scopes))
        payload["banned"] = (request.session.user in app_data["bans"])
        payload["scopes"] = scopes
        payload["redirect_uri"] = redirect_uri
        payload["redirect_allowed"] = ((redirect_uri in app_data["allowed_redirects"]) or ("*" in app_data["allowed_redirects"]))
        return meower.respond(payload, 200, error=False)
    elif request.method == "POST":
        # Check if user is banned
        if request.session.user in app_data["bans"]:
            return meower.respond({"type": "userBannedFromApp"}, 403, error=True)

        # Authorize app
        if not (app_id in userdata["security"]["oauth"]["authorized"]):
            userdata["security"]["oauth"]["authorized"].append(app_id)
            userdata["security"]["oauth"]["scopes"][app_id] = scopes
            meower.db["usersv0"].update_one({"_id": request.session.user}, {"$set": {"security.oauth.authorized": userdata["security"]["oauth"]["authorized"], "security.oauth.scopes": userdata["security"]["oauth"]["scopes"]}})
        
        # Return OAuth exchange session
        session = create_session(4, request.session.user, secrets.token_urlsafe(16), 300, app=app_id, scopes=scopes)
        del session["previous_refresh_tokens"]
        return meower.respond(session, 200, error=False)

@oauth.route("/exchange", methods=["POST"])
def exchange_oauth_code():
    # Check for required data
    if not (("code" in request.json) and ("app" in request.json) and ("secret" in request.json)):
        return meower.respond({"type": "missingField"}, 400, error=True)
 
    # Extract app ID and scopes for simplicity
    code = request.json["code"].strip()
    app_id = request.json["app"].strip()
    secret = request.json["secret"].strip()

    # Check for bad datatypes and syntax
    if not ((type(code) == str) or (type(app_id) == str) or (type(secret) == str)):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif (len(code) > 32) or (len(app_id) > 32) or (len(secret) > 64):
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

    # Get session data
    session = meower.db["sessions"].find_one({"token": code})
    if (session is None) or (session["type"] != 4) or (session["expires"] < time.time()) or (session["user"] != request.session.user) or (session["app"] != app_id) or session["revoked"]:
        return meower.respond({"type": "codeDoesNotExist"}, 401, error=True)

    # Get user data
    userdata = meower.db["usersv0"].find_one({"_id": request.session.user})

    # Get app data
    app_data = meower.db["oauth"].find_one({"_id": app_id})
    if app_data is None:
        return meower.respond({"type": "appDoesNotExist"}, 400, error=True)

    # Check if session is valid
    if app_data["secret"] != secret:
        return meower.respond({"type": "invalidSecret"}, 401, error=True)
    elif request.session.user in app_data["bans"]:
        return meower.respond({"type": "userBannedFromApp"}, 403, error=True)
    elif not ((app_id in userdata["security"]["oauth"]["authorized"]) or (session["scopes"] != userdata["security"]["oauth"]["scopes"][app_id])):
        return meower.respond({"type": "userNotAuthorized"}, 401, error=True)

    # Delete exchange session
    meower.db["sessions"].delete_one({"_id": session["_id"]})

    # Return OAuth full session
    session = create_session(5, request.session.user, generate_token(32), 300, app=session["app"], scopes=session["scopes"])
    del session["previous_refresh_tokens"]
    return meower.respond(session, 200, error=False)
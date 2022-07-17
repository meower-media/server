from threading import Thread
from jinja2 import Template
from flask import Blueprint, request
from flask import current_app as meower
from passlib.hash import scrypt, bcrypt
from hashlib import sha256
import secrets
import string
import pyotp
import time
from uuid import uuid4
import string
import pymongo

oauth = Blueprint("oauth_blueprint", __name__)

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

    # Attempt to authorize the user
    if ("Authorization" in request.headers) or (len(str(request.headers.get("Authorization"))) <= 136):
        request.session = meower.Session(meower, str(request.headers.get("Authorization")).replace("Bearer ", "").strip())
        if request.session.authed:
            request.user = request.session.user
        else:
            request.user = None

@oauth.route("/create", methods=["POST"])
def create_account():
    # Check for account creation block
    if meower.db["netlog"].find_one({"_id": request.remote_addr, "creation_blocked": True}) is not None:
        return meower.respond({"type": "accountCreationBlocked"}, 403, error=True)

    # Check for required data
    meower.check_for_json([{"id": "username", "t": str, "l_min": 1, "l_max": 20}, {"id": "password", "t": str, "l_max": 256}])

    # Extract username and password for simplicity
    username = request.json["username"].strip()
    password = request.json["password"].strip()

    # Check for bad characters
    if meower.check_for_bad_chars_username(username):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)

    # Check if the username is allowed
    for bad_username in meower.blocked_usernames:
        if bad_username.lower() in username.lower():
            return meower.respond({"type": "usernameBlocked", "message": "That username is blocked from being used"}, 400, error=True)

    # Check if account exists
    if meower.db["usersv0"].find_one({"lower_username": username.lower()}) is not None:
        return meower.respond({"type": "usernameAlreadyExists", "message": "That username is already taken"}, 409, error=True)

    # Create userdata
    userdata = {
        "_id": str(uuid4()),
        "username": username,
        "lower_username": username.lower(),
        "state": 0,
        "created": int(time.time()),
        "config": {
            "unread_messages": 0,
            "theme": "orange",
            "mode": True,
            "sfx": True,
            "bgm": {
                "enabled": True,
                "type": 0,
                "data": 2
            }
        },
        "profile": {
            "pfp": {
                "type": 0,
                "data": 1
            },
            "quote": "",
            "status": 1,
            "last_seen": int(time.time())
        },
        "security": {
            "email": None,
            "password": {
                "hash_type": "scrypt",
                "hash": scrypt.hash(sha256(password.encode()).hexdigest())
            },
            "webauthn": [],
            "default_method": "password",
            "totp": None,
            "oauth": {
                "authorized": [],
                "scopes": {}
            },
            "blocked": [],
            "username_history": [
                {
                    "username": username,
                    "timestamp": int(time.time()),
                    "changed_by_admin": False
                }
            ],
            "moderation_history": [],
            "delete_after": None,
            "suspended_until": None,
            "banned": False
        }
    }
    meower.db["usersv0"].insert_one(userdata)

    # Return session
    return meower.respond(meower.foundation_session(userdata["_id"]), 200, error=False)

@oauth.route("/auth-methods", methods=["GET"])
def get_auth_methods():
    # Check for required data
    meower.check_for_json([{"id": "username", "t": str, "l_min": 1, "l_max": 20}])

    # Extract username for simplicity
    username = request.json["username"].strip()

    # Check for bad characters
    if meower.check_for_bad_chars_username(username):
        return meower.respond({"type": "accountDoesNotExist"}, 400, error=True)

    # Make sure account exists and check if it is able to be accessed
    userdata = meower.db["usersv0"].find_one({"lower_username": username.lower()})
    if userdata is None:
        # Account does not exist
        return meower.respond({"type": "accountDoesNotExist"}, 401, error=True)
    elif (userdata["security"]["email"] == None) and (userdata["security"]["password"] == None) and (len(userdata["security"]["webauthn"]) == 0):
        # Account doesn't have any authentication methods
        return meower.respond({"type": "noAuthenticationMethods"}, 401, error=True)

    # Give authentication methods
    methods = []
    if userdata["security"]["email"] is not None:
        methods.append("email")
    if userdata["security"]["password"] is not None:
        methods.append("password")
    if len(userdata["security"]["webauthn"]) > 0:
        methods.append("webauthn")
    return meower.respond({"methods": methods, "default": userdata["security"]["default_method"]}, 200, error=False)

@oauth.route("/login", methods=["POST"])
def login():
    # Check for required data
    meower.check_for_json([{"id": "username", "t": str, "l_min": 1, "l_max": 20}, {"id": "auth_method", "t": str, "l_max": 20}])

    # Extract username and password for simplicity
    username = request.json["username"].strip()
    auth_method = request.json["auth_method"].strip().lower()

    # Make sure the account exists and check account flags
    userdata = meower.db["usersv0"].find_one({"lower_username": username.lower()})
    if userdata is None:
        # Account does not exist
        return meower.respond({"type": "accountDoesNotExist"}, 401, error=True)
    elif userdata["security"]["banned"]:
        # Account is banned
        return meower.respond({"type": "accountBanned"}, 401, error=True)
    
    # Check for valid authentication
    if (auth_method == "password") and (userdata["security"]["password"] is not None):
        meower.check_for_json([{"id": "password", "t": str, "l_max": 256}])
        attempted_password = sha256(request.json["password"].strip().encode()).hexdigest()
        password = userdata["security"]["password"]
        valid = False
        if (password["hash_type"] == "scrypt") and scrypt.verify(attempted_password, password["hash"]):
            valid = True
        elif (password["hash_type"] == "bcrypt") and bcrypt.verify(str(request.json["password"]), password["hash"]):
            # Legacy support for Meower Scratch 4.7-5.6 -- updates to scrypt on first login
            meower.db["usersv0"].update_one({"_id": userdata["_id"]}, {"$set": {"security.password.hash_type": "scrypt", "security.password.hash": scrypt.hash(attempted_password)}})
            valid = True
        elif (password["hash_type"] == "sha256") and (password["hash"] == sha256(attempted_password.encode()).hexdigest()):
            # Legacy support for Meower Scratch 4.5-4.6 -- updates to scrypt on first login
            meower.db["usersv0"].update_one({"_id": userdata["_id"]}, {"$set": {"security.password.hash_type": "scrypt", "security.password.hash": scrypt.hash(attempted_password)}})
            valid = True
        if valid:
            # Return session
            if userdata["security"]["totp"] is not None:
                session = meower.create_session(2, userdata["_id"], secrets.token_urlsafe(64), expires=300)
                minimal_userdata = {}
                for key in ["username", "lower_username", "state", "created"]:
                    minimal_userdata[key] = userdata[key]
                return meower.respond({"session": session, "user": minimal_userdata, "requires_totp": True}, 200, error=False)
            else:
                return meower.respond(meower.foundation_session(userdata["_id"]), 200, error=False)
        else:
            # Invalid password
            return meower.respond({"type": "invalidCredentials"}, 401, error=True)
    elif (auth_method == "email") and (userdata["security"]["email"] is not None):
        if meower.check_for_spam("email_login", userdata["_id"], 60):
            return meower.respond({"type": "tooManyRequests"}, 429, error=True)
        new_code = str("".join(secrets.choice(string.ascii_letters + string.digits) for i in range(8))).upper()
        meower.create_session(0, userdata["_id"], new_code, email=userdata["security"]["email"], expires=600, action="login")
        with open("apiv0/email_templates/confirmations/login_code.html", "r") as f:
            email_template = Template(f.read()).render({"username": userdata["username"], "code": new_code})
        email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
        Thread(target=meower.send_email, args=(email, userdata["username"], "Login confirmation code", email_template,), kwargs={"type": "text/html"}).start()
        return meower.respond({}, 200, error=False)
    elif auth_method == "device":
        new_code = str("".join(secrets.choice(string.ascii_letters + string.digits) for i in range(8))).upper()
        session = meower.create_session(1, userdata["_id"], new_code, expires=300)
        minimal_userdata = {}
        for key in ["username", "lower_username", "state", "created"]:
            minimal_userdata[key] = userdata[key]
        return meower.respond({"session": session, "user": minimal_userdata, "requires_totp": False}, 200, error=False)
    else:
        return meower.respond({"type": "unknownMethod", "message": "Authentication method unavailable"}, 400, error=True)

@oauth.route("/login/totp", methods=["POST"])
def login_totp():
    # Check whether the client is authenticated
    meower.require_auth([2])

    # Check for required data
    meower.check_for_json([{"id": "totp", "t": str, "l_min": 6, "l_max": 8}])
    
    # Get user data from database
    userdata = meower.db["usersv0"].find_one({"_id": request.session.user})

    # Check for valid authentication
    if (userdata["security"]["totp"] is None) or pyotp.TOTP(userdata["security"]["totp"]["secret"]).verify(request.json["totp"]) or (request.json["totp"] in userdata["security"]["totp"]["recovery_codes"]):
        # Delete session
        request.session.delete()
    
        # Full account session
        return meower.respond(meower.foundation_session(request.session.user), 200, error=False)
    else:
        # Invalid TOTP code
        return meower.respond({"type": "invalidCredentials", "message": "Invalid TOTP code"}, 401, error=True)

@oauth.route("/login/email", methods=["POST"])
def login_email():
    # Check for required data
    meower.check_for_json([{"id": "username", "t": str, "l_min": 1, "l_max": 20}, {"id": "code", "t": str, "l_min": 8, "l_max": 8}])

    # Extract username and given code for simplicity
    username = request.json["username"].strip().lower()
    code = request.json["code"].strip().upper()

    # Check for bad characters
    if meower.check_for_bad_chars_username(username):
        return meower.respond({"type": "illegalCharacters"}, 400, error=True)

    # Get userdata from database
    userdata = meower.db["usersv0"].find_one({"lower_username": username})

    # Get session data from database
    session_data = meower.db["sessions"].find_one({"token": code})
    if (session_data is None) or (session_data["type"] != 0) or (session_data["user"] != userdata["_id"]) or (session_data["expires"] < time.time()) or (session_data["email"] != userdata["security"]["email"]):
        return meower.respond({"type": "invalidCredentials"}, 401, error=True)
    else:
        # Delete session
        meower.db["sessions"].delete_one({"_id": session_data["_id"]})
    
        # Full account session
        return meower.respond(meower.foundation_session(userdata["_id"]), 200, error=False)

@oauth.route("/login/device", methods=["GET"])
def login_device():
    # Check whether the client is authenticated
    meower.require_auth([1])

    # Delete session
    request.session.delete()

    # Full account session
    return meower.respond(meower.foundation_session(request.session.user), 200, error=False)

@oauth.route("/session", methods=["GET", "DELETE"])
def current_session():
    # Check whether the client is authenticated
    meower.require_auth([3, 5])

    if request.method == "GET":
        # Get session data from database
        session = request.session.json.copy()
        session["refresh_token"] = None
        session["previous_refresh_tokens"] = None

        # Get user data
        user = meower.User(meower, user_id=session["user"])

        # Return session data
        return meower.respond({"session": session, "user": user.client, "foundation_session": (session["type"] == 3), "oauth_session": (session["type"] == 5)}, 200, error=False)
    elif request.method == "DELETE":
        # Delete session
        request.session.delete()
        return meower.respond({}, 200, error=False)

@oauth.route("/session/refresh", methods=["POST"])
def refresh_session():
    # Check whether the client is authenticated
    if ("Authorization" in request.headers) or (len(str(request.headers.get("Authorization"))) <= 136):
        session = str(request.headers.get("Authorization").replace("Bearer ", "")).strip()

    # Check for bad datatypes and syntax
    if not (type(session) == str):
        return meower.respond({"type": "badDatatype"}, 400, error=True)
    elif len(session) >= 128:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

    # Check for token reuse
    meower.db["sessions"].delete_many({"previous_renew_tokens": {"$all": [session]}})

    # Get token data
    session_data = meower.db["sessions"].find_one({"refresh_token": session})
    if (session_data is None) or (session_data["type"] != 5) or (session_data["refresh_expires"] < time.time()):
        return meower.respond({"type": "tokenDoesNotExist"}, 400, error=True)
    else:
        # Refresh token
        session_data["token"] = secrets.token_urlsafe(64)
        session_data["expires"] = time.time() + 1800
        session_data["refresh_token"] = secrets.token_urlsafe(128)
        session_data["previous_refresh_tokens"].append(session)
        meower.db["sessions"].update_one({"_id": session_data["_id"]}, {"$set": session_data})
        userdata = meower.db["usersv0"].find_one({"_id": session_data["user"]})
        del userdata["security"]
        return meower.respond({"session": session_data, "user": userdata, "requires_totp": False}, 200, error=False)

@oauth.route("/authorize/device", methods=["POST"])
def authorize_device():
    # Check whether the client is authenticated
    meower.require_auth([3])

    # Check for required data
    meower.check_for_json([{"id": "code", "t": str, "l_min": 8, "l_max": 8}])

    # Extract code for simplicity
    code = request.json["code"].strip().upper()

    # Get session data
    session = meower.db["sessions"].find_one({"token": code})

    # Check if the session is invalid
    if (session is None) or (session["type"] != 1) or (session["expires"] < time.time()) or (session["user"] != request.session.user) or session["verified"]:
        return meower.respond({"type": "codeDoesNotExist"}, 400, error=True)
    else:
        # Verify session
        meower.db["sessions"].update_one({"_id": session["_id"]}, {"$set": {"verified": True}})
        return meower.respond({}, 200, error=False)

@oauth.route("/authorize/app", methods=["GET", "POST"])
def authorize_app():
    # Check whether the client is authenticated
    meower.require_auth([3])

    # Check for required data
    meower.check_for_json([{"id": "app", "t": str, "l_min": 1, "l_max": 50}, {"id": "scopes", "t": str, "l_max": 1000}, {"id": "redirect_uri", "t": str, "l_max": 1000}])
 
    # Extract app ID and scopes for simplicity
    app_id = request.json["app"].strip()
    scopes = request.json["scopes"].strip().split(" ")
    redirect_uri = request.json["redirect_uri"].strip()

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
        session = meower.create_session(4, request.session.user, secrets.token_urlsafe(16), 300, app=app_id, scopes=scopes)
        return meower.respond(session, 200, error=False)

@oauth.route("/exchange", methods=["POST"])
def exchange_oauth_code():
    # Check for required data
    meower.check_for_json([{"id": "code", "t": str, "l_max": 32}, {"id": "app", "t": str, "l_max": 50}, {"id": "secret", "t": str, "l_min": 0, "l_max": 64}])
 
    # Extract app ID and scopes for simplicity
    code = request.json["code"].strip()
    app_id = request.json["app"].strip()
    secret = request.json["secret"].strip()

    # Get session data
    session = meower.db["sessions"].find_one({"token": code})
    if (session is None) or (session["type"] != 4) or (session["expires"] < time.time()) or (session["app"] != app_id):
        return meower.respond({"type": "codeDoesNotExist"}, 401, error=True)

    # Get user data
    userdata = meower.db["usersv0"].find_one({"_id": session["user"]})

    # Get app data
    app_data = meower.db["oauth"].find_one({"_id": app_id})
    if app_data is None:
        return meower.respond({"type": "appDoesNotExist"}, 400, error=True)

    # Check if session is valid
    if app_data["secret"] != secret:
        return meower.respond({"type": "invalidSecret"}, 401, error=True)
    elif session["user"] in app_data["bans"]:
        return meower.respond({"type": "userBannedFromApp"}, 403, error=True)
    elif not ((app_id in userdata["security"]["oauth"]["authorized"]) or (session["scopes"] != userdata["security"]["oauth"]["scopes"][app_id])):
        return meower.respond({"type": "userNotAuthorized"}, 401, error=True)

    # Delete exchange session
    meower.db["sessions"].delete_one({"_id": session["_id"]})

    # Return OAuth full session
    session = meower.create_session(5, session["user"], secrets.token_urlsafe(32), expires=1800, app=session["app"], scopes=session["scopes"])
    session["previous_refresh_tokens"] = None
    return meower.respond(session, 200, error=False)

@oauth.route("/apps", methods=["GET", "POST", "PATCH", "DELETE"])
def manage_oauth_apps():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:oauth:apps")

    if request.method == "GET": # Get all OAuth apps
        apps = meower.db["oauth"].find({"owner": request.session.user}).sort("name", pymongo.ASCENDING)
        return meower.respond({"apps": list(apps)}, 200, error=False)
    elif request.method == "POST": # Create new OAuth app
        # Check for required data
        meower.check_for_json([{"id": "name", "t": str, "l_min": 1, "l_max": 20}])

        # Extract app name for simplicity
        name = request.json["name"].strip()

        # Check if user has too many apps
        apps_count = meower.db["oauth"].count_documents({"owner": request.session.user})
        if apps_count >= 50:
            return meower.respond({"type": "tooManyApps"}, 403, error=True)

        # Craete app data
        app_data = {
            "_id": str(uuid4()),
            "owner": request.session.user,
            "name": name,
            "description": "",
            "first_party": False,
            "bans": [],
            "allowed_redirects": [],
            "secret": secrets.token_urlsafe(64),
            "created": time.time()
        }

        # Add app data to database
        meower.db["oauth"].insert_one(app_data)

        # Return app data to user
        return meower.respond(app_data, 200, error=False)

@oauth.route("/apps/<app_id>", methods=["GET", "PATCH", "DELETE"])
def manage_oauth_app(app_id):
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:oauth:apps")

    # Check for bad syntax
    if len(app_id) > 32:
        return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

    # Get app data
    app_data = meower.db["oauth"].find_one({"_id": app_id})
    if (app_data is None) or (app_data["owner"] != request.session.user):
        return meower.respond({"type": "notFound", "message": "Requested OAuth app was not found"}, 404, error=True)

    # Check for required data
    if request.method == "GET": # Return app data
        return meower.respond(app_data, 200, error=False)
    elif request.method == "PATCH": # Update app data
        # Update owner
        if ("owner" in request.json) and (len(request.json["owner"]) < 32):
            userdata = meower.db["usersv0"].find_one({"_id": request.json["owner"]})
            if userdata is None:
                return meower.respond({"type": "userDoesNotExist"}, 400, error=True)
            elif userdata["_id"] == request.session.user:
                return meower.respond({"type": "cannotChangeOwnerToSelf", "message": "You cannot change the owner to yourself"}, 400, error=True)
            else:
                app_data["owner"] = request.json["owner"]
                meower.db["oauth"].update_one({"_id": app_id}, {"$set": {"owner": request.json["owner"]}})

        # Update name
        if ("name" in request.json) and (len(request.json["name"]) < 20):
            app_data["name"] = request.json["name"]
            meower.db["oauth"].update_one({"_id": app_id}, {"$set": {"name": request.json["name"]}})

        # Update description
        if ("description" in request.json) and (len(request.json["description"]) < 200):
            app_data["description"] = request.json["description"]
            meower.db["oauth"].update_one({"_id": app_id}, {"$set": {"description": request.json["description"]}})

        # Add bans
        if ("add_bans" in request.json) and (type(request.json["add_bans"]) == list):
            for user in request.json["add_bans"]:
                userdata = meower.db["usersv0"].find_one({"_id": user})
                if (userdata is None) and (user not in app_data["bans"]):
                    app_data["bans"].append(user)
            meower.db["oauth"].update_one({"_id": app_id}, {"$set": {"bans": app_data["bans"]}})
        
        # Remove bans
        if ("remove_bans" in request.json) and (type(request.json["remove_bans"]) == list):
            for user in request.json["remove_bans"]:
                if user in app_data["bans"]:
                    app_data["bans"].remove(user)
            meower.db["oauth"].update_one({"_id": app_id}, {"$set": {"bans": app_data["bans"]}})

        # Add bans
        if ("add_redirects" in request.json) and (type(request.json["add_redirects"]) == list):
            for user in request.json["add_redirects"]:
                if user not in app_data["allowed_redirects"]:
                    app_data["allowed_redirects"].append(user)
            meower.db["oauth"].update_one({"_id": app_id}, {"$set": {"allowed_redirects": app_data["allowed_redirects"]}})
        
        # Remove bans
        if ("remove_redirects" in request.json) and (type(request.json["remove_redirects"]) == list):
            for user in request.json["remove_redirects"]:
                if user in app_data["allowed_redirects"]:
                    app_data["allowed_redirects"].remove(user)
            meower.db["oauth"].update_one({"_id": app_id}, {"$set": {"allowed_redirects": app_data["allowed_redirects"]}})

        # Refresh secret
        if ("refresh_secret" in request.json) and (request.json["refresh_secret"] == True):
            app_data["secret"] = secrets.token_urlsafe(64)
            meower.db["oauth"].update_one({"_id": app_id}, {"$set": {"secret": app_data["secret"]}})

        # Return new app data
        return meower.respond(app_data, 200, error=False)
    elif request.method == "DELETE": # Delete app
        meower.db["oauth"].delete_one({"_id": app_id})
        return meower.respond({}, 200, error=False)
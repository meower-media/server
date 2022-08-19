import re
from threading import Thread
from jinja2 import Template
from flask import Blueprint, request
from flask import current_app as meower
from passlib.hash import scrypt, bcrypt
from hashlib import sha256
import pyotp
from webauthn import generate_registration_options, options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
)
import secrets
import string
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
        return meower.resp("ipBlocked")

    # Attempt to authorize the user
    if ("Authorization" in request.headers) and (len(str(request.headers.get("Authorization"))) <= 136):
        request.session = meower.Session(meower, str(request.headers.get("Authorization")).replace("Bearer ", "").strip())
        if request.session.authed:
            request.user = request.session.user
        else:
            request.user = None

@oauth.route("/create", methods=["POST"])
def create_account():
    # Check for account creation block
    if meower.db.netlog.find_one({"_id": request.remote_addr, "creation_blocked": True}) is not None:
        return meower.resp(403, msg="Account creation is blocked on your IP")

    # Check for required data
    meower.check_for_json([{"id": "username", "t": str, "l_min": 1, "l_max": 20}, {"id": "password", "t": str, "l_max": 256}, {"id": "child", "t": bool}, {"id": "captcha", "t": str, "l_min": 1, "l_max": 1024}])

    # Extract username and password for simplicity
    username = request.json["username"].strip()
    password = request.json["password"].strip()

    # Check for bad characters
    if meower.check_for_bad_chars_username(username):
        return meower.resp(400, msg="Username has an illegal character")

    # Check if the username is allowed
    for bad_username in meower.blocked_usernames:
        if bad_username.lower() in username.lower():
            return meower.resp(409, msg="Username already taken")

    # Check if account exists
    if meower.db.users.find_one({"lower_username": username.lower()}) is not None:
        return meower.resp(409, msg="Username already taken")

    # Check captcha
    #if not meower.check_captcha(request.json["captcha"]):
        #return meower.resp(403, msg="Invalid captcha")

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
            "pfp": "",
            "quote": "",
            "status": 1,
            "last_seen": int(time.time())
        },
        "security": {
            "email": None,
            "password": {
                "type": "scrypt",
                "hash": scrypt.hash(sha256(password.encode()).hexdigest())
            },
            "webauthn": [],
            "totp": None,
            "last_ip": None,
            "delete_after": None,
            "banned_until": None
        },
        "authorized_oauth": {},
        "privacy": {
            "friend_requests": True,
            "dm_requests": True,
            "blocked": []
        },
        "guardian": {
            "child": request.json["child"],
            "linked_guardian": None,
            "account_disabled": False,
            "filter_level": 0,
            "user_whitelist": False,
            "community_whitelist": False,
            "groups_enabled": True,
            "encrypted_chats": True,
            "allowed_users": [],
            "blocked_users": [],
            "allowed_communities": [],
            "blocked_communities": [],
        }
    }
    meower.db.users.insert_one(userdata)

    # Return session
    return meower.resp(200, meower.foundation_session(userdata["_id"], "your password"))

@oauth.route("/login/<username>", methods=["GET"])
def login_begin(username):
    if len(username) > 20:
        return meower.resp(401, msg="Invalid username")
    username = username.strip()

    # Check for bad characters
    if meower.check_for_bad_chars_username(username):
        return meower.resp(401, msg="Invalid username")

    # Get user data
    userdata = meower.db.users.find_one({"lower_username": username.lower()})
    if userdata is None:
        # Account does not exist
        return meower.resp(401, msg="Invalid username")

    # Get authentication method
    auth_method = None
    if userdata["security"]["password"] is not None:
        auth_method = "password"
    elif len(userdata["security"]["webauthn"]) > 0:
        auth_method = "webauthn"
    elif userdata["security"]["email"] is not None:
        auth_method = "email"
    
    # Return authentication method, pfp, and theme
    return meower.resp(200, {"auth_method": auth_method})

@oauth.route("/login/<username>/password", methods=["POST"])
def login_password(username):
    # Check for required data
    meower.check_for_json([{"id": "password", "t": str, "l_min": 1, "l_max": 64}])

    # Extract username and password for simplicity
    username = username.strip().lower()
    password = request.json["password"].strip()

    # Get user data
    userdata = meower.db.users.find_one({"lower_username": username})
    if userdata is None:
        # Account does not exist
        return meower.resp(401, msg="Invalid username")

    # Check if user has had too many failed attempts
    meower.check_ratelimit("password", userdata["_id"])

    # Check if password is correct
    stored_pswd = userdata["security"]["password"]
    if stored_pswd is None:
        return meower.resp(400, msg="Invalid authentication method")
    elif stored_pswd["type"] == "scrypt":
        # Verify scrypt password
        password = sha256(password.encode()).hexdigest()
        if not scrypt.verify(password, stored_pswd["hash"]):
            meower.ratelimit("password", userdata["_id"], burst=5, seconds=60)
            return meower.resp(401, msg="Incorrect password")
    elif stored_pswd["type"] == "bcrypt":
        # Verify legacy bcrypt password
        if not bcrypt.verify(password, stored_pswd["hash"]):
            meower.ratelimit("password", userdata["_id"], burst=5, seconds=60)
            return meower.resp(401, msg="Incorrect password")
        else:
            # Update bcrypt password to scrypt password
            password = sha256(password.encode()).hexdigest()
            meower.db.users.update_one({"_id": userdata["_id"]}, {"$set": {"security.password.type": "scrypt", "security.password.hash": scrypt.hash(password)}})

    # Check TOTP 2FA
    if userdata["security"]["totp"] is not None:
        meower.check_for_json([{"id": "totp", "t": str, "l_min": 6, "l_max": 10}])

        # Check if user has had too many failed attempts
        meower.check_ratelimit("totp", userdata["_id"])

        totp_code = request.json["totp"].replace("-", "")
        if (not pyotp.TOTP(userdata["security"]["totp"]["secret"]).verify(totp_code)) and (totp_code not in userdata["security"]["totp"]["recovery"]):
            meower.ratelimit("totp", userdata["_id"], burst=5, seconds=60)
            return meower.resp(401, msg="Invalid TOTP")
        elif totp_code in userdata["security"]["totp"]["recovery"]:
            userdata["security"]["totp"]["recovery"].remove(totp_code)
            meower.db.users.update_one({"_id": userdata["_id"]}, {"$set": {"security.totp.recovery": userdata["security"]["totp"]["recovery"]}})

    # Return response
    return meower.resp(200, meower.foundation_session(userdata["_id"], "your password"))

@oauth.route("/login/<username>/webauthn", methods=["POST"])
def login_webauthn(username):
    return meower.resp(501)

@oauth.route("/login/<username>/email", methods=["GET", "POST"])
def login_email(username):
    # Extract username for simplicity
    username = username.strip().lower()

    # Get user data
    userdata = meower.db.users.find_one({"lower_username": username})
    if userdata is None:
        # Account does not exist
        return meower.resp(401)
    
    # Get email
    if userdata["security"]["email"] is not None:
        email = meower.decrypt(userdata["security"]["email"])
    else:
        # Email is not set
        if request.method == "GET":
            return meower.resp(200)
        elif request.method == "POST":
            return meower.resp(401)

    if request.method == "GET":
        # Generate email verification code
        code = str("".join(secrets.choice(string.ascii_letters + string.digits) for i in range(8))).upper()
        meower.create_session(0, userdata["_id"], code, email=userdata["security"]["email"], expires=600, action="login")

        # Send email
        meower.send_email(email, "confirmations/login_code", {"username": userdata["username"], "subject": "Login verification code", "code": code})

        return meower.resp(200)
    elif request.method == "POST":
        # Check for required data
        meower.check_for_json([{"id": "code", "t": str, "l_min": 1, "l_max": 8}])

        # Check code
        code = request.json["code"].upper()
        session = meower.db.sessions.find_one({"user": userdata["_id"], "type": 0, "action": "login", "token": code})
        if session is None:
            return meower.resp(401)
        else:
            # Delete session
            meower.db.sessions.delete_one({"_id": session["_id"]})

            # Return session
            return meower.resp(200, meower.foundation_session(userdata["_id"], "email"))

@oauth.route("/login/device", methods=["GET"])
def login_device():
    # Check whether the client is authenticated
    meower.require_auth([1])

    # Delete session
    request.session.delete()

    # Full account session
    return meower.resp(200, meower.foundation_session(request.user._id, "another device"))

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
        return meower.resp(200, {"session": session, "user": user.client, "foundation_session": (session["type"] == 3), "oauth_session": (session["type"] == 5)})
    elif request.method == "DELETE":
        # Delete session
        request.session.delete()
        return meower.resp("empty")

@oauth.route("/session/refresh", methods=["POST"])
def refresh_session():
    # Check whether the client is authenticated
    if ("Authorization" in request.headers) or (len(str(request.headers.get("Authorization"))) <= 136):
        session = str(request.headers.get("Authorization").replace("Bearer ", "")).strip()

    # Check for bad datatypes and syntax
    if not (type(session) == str):
        return meower.resp(422)
    elif len(session) >= 128:
        return meower.resp(413)

    # Check for token reuse
    meower.db.sessions.delete_many({"previous_renew_tokens": {"$all": [session]}})

    # Get token data
    session_data = meower.db.sessions.find_one({"refresh_token": session})
    if (session_data is None) or (session_data["type"] != 5) or (session_data["refresh_expires"] < time.time()):
        return meower.resp({"type": "tokenDoesNotExist"}, 400, error=True)
    else:
        # Refresh token
        session_data["token"] = secrets.token_urlsafe(64)
        session_data["expires"] = time.time() + 1800
        session_data["refresh_token"] = secrets.token_urlsafe(128)
        session_data["previous_refresh_tokens"].append(session)
        meower.db.sessions.update_one({"_id": session_data["_id"]}, {"$set": session_data})
        userdata = meower.db.users.find_one({"_id": session_data["user"]})
        del userdata["security"]
        return meower.resp(200, {"session": session_data, "user": userdata, "requires_totp": False})

@oauth.route("/authorize/device", methods=["POST"])
def authorize_device():
    # Check whether the client is authenticated
    meower.require_auth([3])

    # Check for required data
    meower.check_for_json([{"id": "code", "t": str, "l_min": 8, "l_max": 8}])

    # Extract code for simplicity
    code = request.json["code"].strip().upper()

    # Get session data
    session = meower.db.sessions.find_one({"token": code})

    # Check if the session is invalid
    if (session is None) or (session["type"] != 1) or (session["expires"] < time.time()) or (session["user"] != request.user._id) or session["verified"]:
        return meower.resp({"type": "codeDoesNotExist"}, 400, error=True)
    else:
        # Verify session
        meower.db.sessions.update_one({"_id": session["_id"]}, {"$set": {"verified": True}})
        return meower.resp("empty")

@oauth.route("/authorize/app", methods=["GET", "POST"])
def authorize_app():
    # Check whether the client is authenticated
    meower.require_auth([3])

    # Check for required data
    meower.check_for_json([{"id": "app", "t": str, "l_min": 1, "l_max": 50}, {"id": "scopes", "t": str, "l_max": 1000}, {"id": "redirect_uri", "t": str, "l_max": 1000}])
 
    # Extract app ID and scopes for simplicity
    app_id = request.json["app"].strip()
    scopes = set(request.json["scopes"].strip().split(" "))
    redirect_uri = request.json["redirect_uri"].strip()

    # Get app data
    app_data = meower.db.oauth.find_one({"_id": app_id})
    # Check if the app exists
    if app_data is None:
        return meower.resp({"type": "appDoesNotExist"}, 400, error=True)

    # Apply the "all" scope
    if "all" in scopes:
        scopes = scopes.union(meower.all_oauth_scopes)
        if app_data["first_party"]:
            scopes = scopes.union(meower.first_party_oauth_scopes)

    # Validate all scopes
    remove_scopes = []
    for scope in scopes:
        if (scope != "all") and (scope not in meower.all_oauth_scopes) and (app_data["first_party"] and (scope not in meower.first_party_oauth_scopes)):
            remove_scopes.append(scope)
    for scope in remove_scopes:
        scopes.remove(scope)

    # Convert scopes back to list from set
    scopes = list(scopes)

    # Get user data
    userdata = meower.db.users.find_one({"_id": request.user._id})

    if request.method == "GET":
        # Return app information
        payload = app_data.copy()
        del payload["bans"]
        del payload["allowed_redirects"]
        del payload["secret"]
        payload["authorized"] = ((app_id in userdata["security"]["oauth"]["authorized"]) and (userdata["security"]["oauth"]["scopes"][app_id] == scopes))
        payload["banned"] = (request.user._id in app_data["bans"])
        payload["scopes"] = scopes
        payload["redirect_uri"] = redirect_uri
        payload["redirect_allowed"] = ((redirect_uri in app_data["allowed_redirects"]) or ("*" in app_data["allowed_redirects"]))
        return meower.resp(200, payload)
    elif request.method == "POST":
        # Check if user is banned
        if request.user._id in app_data["bans"]:
            return meower.resp({"type": "userBannedFromApp"}, 403, error=True)

        # Authorize app
        if not (app_id in userdata["security"]["oauth"]["authorized"]):
            userdata["security"]["oauth"]["authorized"].append(app_id)
            userdata["security"]["oauth"]["scopes"][app_id] = scopes
            meower.db.users.update_one({"_id": request.user._id}, {"$set": {"security.oauth.authorized": userdata["security"]["oauth"]["authorized"], "security.oauth.scopes": userdata["security"]["oauth"]["scopes"]}})
        
        # Return OAuth exchange session
        session = meower.create_session(4, request.user._id, secrets.token_urlsafe(16), 300, app=app_id, scopes=scopes)
        return meower.resp(200, session)

@oauth.route("/exchange", methods=["POST"])
def exchange_oauth_code():
    # Check for required data
    meower.check_for_json([{"id": "code", "t": str, "l_max": 32}, {"id": "app", "t": str, "l_max": 50}, {"id": "secret", "t": str, "l_min": 0, "l_max": 64}])
 
    # Extract app ID and scopes for simplicity
    code = request.json["code"].strip()
    app_id = request.json["app"].strip()
    secret = request.json["secret"].strip()

    # Get session data
    session = meower.db.sessions.find_one({"token": code})
    if (session is None) or (session["type"] != 4) or (session["expires"] < time.time()) or (session["app"] != app_id):
        return meower.resp({"type": "codeDoesNotExist"}, 401, error=True)

    # Get user data
    userdata = meower.db.users.find_one({"_id": session["user"]})

    # Get app data
    app_data = meower.db.oauth.find_one({"_id": app_id})
    if app_data is None:
        return meower.resp({"type": "appDoesNotExist"}, 400, error=True)

    # Check if session is valid
    if app_data["secret"] != secret:
        return meower.resp({"type": "invalidSecret"}, 401, error=True)
    elif session["user"] in app_data["bans"]:
        return meower.resp({"type": "userBannedFromApp"}, 403, error=True)
    elif not ((app_id in userdata["security"]["oauth"]["authorized"]) or (session["scopes"] != userdata["security"]["oauth"]["scopes"][app_id])):
        return meower.resp(401)

    # Delete exchange session
    meower.db.sessions.delete_one({"_id": session["_id"]})

    # Return OAuth full session
    session = meower.create_session(5, session["user"], secrets.token_urlsafe(32), expires=1800, app=session["app"], scopes=session["scopes"])
    session["previous_refresh_tokens"] = None
    return meower.resp(200, session)

@oauth.route("/apps", methods=["GET", "POST", "PATCH", "DELETE"])
def manage_oauth_apps():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:oauth:apps")

    if request.method == "GET": # Get all OAuth apps
        apps = meower.db.oauth.find({"owner": request.user._id}).sort("name", pymongo.ASCENDING)
        return meower.resp(200, {"apps": list(apps)})
    elif request.method == "POST": # Create new OAuth app
        # Check for required data
        meower.check_for_json([{"id": "name", "t": str, "l_min": 1, "l_max": 20}])

        # Extract app name for simplicity
        name = request.json["name"].strip()

        # Check if user has too many apps
        apps_count = meower.db.oauth.count_documents({"owner": request.user._id})
        if apps_count >= 50:
            return meower.resp({"type": "tooManyApps"}, 403, error=True)

        # Craete app data
        app_data = {
            "_id": str(uuid4()),
            "owner": request.user._id,
            "name": name,
            "description": "",
            "first_party": False,
            "bans": [],
            "allowed_redirects": [],
            "secret": secrets.token_urlsafe(64),
            "created": time.time()
        }

        # Add app data to database
        meower.db.oauth.insert_one(app_data)

        # Return app data to user
        return meower.resp(200, app_data)

@oauth.route("/apps/<app_id>", methods=["GET", "PATCH", "DELETE"])
def manage_oauth_app(app_id):
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:oauth:apps")

    # Check for bad syntax
    if len(app_id) > 32:
        return meower.resp(413)

    # Get app data
    app_data = meower.db.oauth.find_one({"_id": app_id})
    if (app_data is None) or (app_data["owner"] != request.user._id):
        return meower.resp({"type": "notFound", "message": "Requested OAuth app was not found"}, 404, error=True)

    # Check for required data
    if request.method == "GET": # Return app data
        return meower.resp(200, app_data)
    elif request.method == "PATCH": # Update app data
        # Update owner
        if ("owner" in request.json) and (len(request.json["owner"]) < 32):
            userdata = meower.db.users.find_one({"_id": request.json["owner"]})
            if userdata is None:
                return meower.resp({"type": "userDoesNotExist"}, 400, error=True)
            elif userdata["_id"] == request.user._id:
                return meower.resp({"type": "cannotChangeOwnerToSelf", "message": "You cannot change the owner to yourself"}, 400, error=True)
            else:
                app_data["owner"] = request.json["owner"]
                meower.db.oauth.update_one({"_id": app_id}, {"$set": {"owner": request.json["owner"]}})

        # Update name
        if ("name" in request.json) and (len(request.json["name"]) < 20):
            app_data["name"] = request.json["name"]
            meower.db.oauth.update_one({"_id": app_id}, {"$set": {"name": request.json["name"]}})

        # Update description
        if ("description" in request.json) and (len(request.json["description"]) < 200):
            app_data["description"] = request.json["description"]
            meower.db.oauth.update_one({"_id": app_id}, {"$set": {"description": request.json["description"]}})

        # Add bans
        if ("add_bans" in request.json) and (type(request.json["add_bans"]) == list):
            for user in request.json["add_bans"]:
                userdata = meower.db.users.find_one({"_id": user})
                if (userdata is None) and (user not in app_data["bans"]):
                    app_data["bans"].append(user)
            meower.db.oauth.update_one({"_id": app_id}, {"$set": {"bans": app_data["bans"]}})
        
        # Remove bans
        if ("remove_bans" in request.json) and (type(request.json["remove_bans"]) == list):
            for user in request.json["remove_bans"]:
                if user in app_data["bans"]:
                    app_data["bans"].remove(user)
            meower.db.oauth.update_one({"_id": app_id}, {"$set": {"bans": app_data["bans"]}})

        # Add bans
        if ("add_redirects" in request.json) and (type(request.json["add_redirects"]) == list):
            for user in request.json["add_redirects"]:
                if user not in app_data["allowed_redirects"]:
                    app_data["allowed_redirects"].append(user)
            meower.db.oauth.update_one({"_id": app_id}, {"$set": {"allowed_redirects": app_data["allowed_redirects"]}})
        
        # Remove bans
        if ("remove_redirects" in request.json) and (type(request.json["remove_redirects"]) == list):
            for user in request.json["remove_redirects"]:
                if user in app_data["allowed_redirects"]:
                    app_data["allowed_redirects"].remove(user)
            meower.db.oauth.update_one({"_id": app_id}, {"$set": {"allowed_redirects": app_data["allowed_redirects"]}})

        # Refresh secret
        if ("refresh_secret" in request.json) and (request.json["refresh_secret"] == True):
            app_data["secret"] = secrets.token_urlsafe(64)
            meower.db.oauth.update_one({"_id": app_id}, {"$set": {"secret": app_data["secret"]}})

        # Return new app data
        return meower.resp(200, app_data)
    elif request.method == "DELETE": # Delete app
        meower.db.oauth.delete_one({"_id": app_id})
        return meower.resp("empty")
from jinja2 import Template
from flask import Blueprint, request
from flask import current_app as meower
from passlib.hash import scrypt
from hashlib import sha256
import secrets
import pyotp
import string
import secrets
from threading import Thread

settings = Blueprint("settings_blueprint", __name__)

@settings.route("/auth-methods", methods=["GET"])
def auth_methods():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:settings:authentication")

    # Get user data
    userdata = meower.db.users.find_one({"_id": request.user._id})

    # Get email address
    if userdata["security"]["email"] is None:
        email = None
    else:
        email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])

    # Password and TOTP
    password = (userdata["security"]["password"] is not None)
    totp = (userdata["security"]["totp"] is not None)

    # WebAuthn
    webauthn = []
    for item in userdata["security"]["webauthn"]:
        pass # To be implementated later

    # Return payload
    return meower.resp(200, {"email": email, "password": password, "totp": totp, "webauthn": webauthn})

@settings.route("/email", methods=["GET", "PATCH"])
def email_address():
    # Get user data
    userdata = meower.db.users.find_one({"_id": request.user._id})

    if request.method == "GET":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="foundation:settings:read_email")

        # Get email address
        if userdata["security"]["email"] is None:
            email = None
        else:
            email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])

        # Return the email address
        return meower.resp(200, {"email": email})
    elif request.method == "PATCH":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="foundation:settings:authentication")

        # Check for required data
        meower.check_for_json([{"id": "email", "t": str, "l_min": 5, "l_max": 100}])

        # Check if TOTP is required and if it is valid
        if userdata["security"]["totp"] is not None:
            # Check for required data
            meower.check_for_json({"id": "totp", "t": str, "l_min": 6, "l_max": 6})

            # Check if it's valid
            if not (pyotp.TOTP(userdata["security"]["totp"]["secret"]).verify(request.json["totp"]) or (request.json["totp"] in userdata["security"]["totp"]["recovery_codes"])):
                return meower.resp({"type": "invalidCredentials", "message": "Invalid TOTP code"}, 401, error=True)

        # Extract email for simplicity
        email = request.json["email"].strip()

        # Create email verification session
        encryption_id, encrypted_email = meower.encrypt(email)
        token = secrets.token_urlsafe(32)
        meower.create_session(0, request.user._id, token, email={"encryption_id": encryption_id, "encrypted_email": encrypted_email}, expires=3600, action="verify")

        # Render and send email
        with open("apiv0/email_templates/confirmations/email_verification.html", "r") as f:
            email_template = Template(f.read()).render({"username": userdata["username"], "token": token})
        Thread(target=meower.send_email, args=(email, userdata["username"], "Verify your email address", email_template,), kwargs={"type": "text/html"}).start()

        # Return payload
        return meower.resp("empty")

@settings.route("/password", methods=["GET", "PATCH", "DELETE"])
def password():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:settings:authentication")

    # Get user data
    userdata = meower.db.users.find_one({"_id": request.user._id})

    if request.method == "GET":
        # Return whether the account has a password
        return meower.resp(200, {"password": (userdata["security"]["password"] is not None)})
    elif request.method == "PATCH":
        # Check for required data
        meower.check_for_json([{"id": "password", "t": str, "l_min": 0, "l_max": 256}])

        # Check if TOTP is required and if it is valid
        if userdata["security"]["totp"] is not None:
            # Check for required data
            meower.check_for_json({"id": "totp", "t": str, "l_min": 6, "l_max": 6})

            # Check if it's valid
            if not (pyotp.TOTP(userdata["security"]["totp"]["secret"]).verify(request.json["totp"]) or (request.json["totp"] in userdata["security"]["totp"]["recovery_codes"])):
                return meower.resp({"type": "invalidCredentials", "message": "Invalid TOTP code"}, 401, error=True)

        # Extract new password for simplicity
        password = request.json["password"].strip()

        # Change password
        hashed_password = scrypt.hash(sha256(password.encode()).hexdigest())
        meower.db.users.update_one({"_id": request.user._id}, {"$set": {"security.password": {"hash_type": "scrypt", "hash": hashed_password}}})

        # Render and send security alert email
        if userdata["security"]["email"] is None:
            email = None
        else:
            email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
        if email is not None:
            with open("apiv0/email_templates/alerts/password_changed.html", "r") as f:
                email_template = Template(f.read()).render({"username": userdata["username"]})
            Thread(target=meower.send_email, args=(email, userdata["username"], "Security Alert", email_template,), kwargs={"type": "text/html"}).start()

        # Return success
        return meower.resp("empty")
    elif request.method == "DELETE":
        # Check if account already has a password
        if userdata["security"]["password"] is None:
            return meower.resp({"type": "totpAlreadyDisabled", "message": "Password already disabled"}, 401, error=True)

        # Check if account is eligible for password removal
        if (userdata["security"]["email"] is None) and (len(userdata["security"]["webauthn"]) == 0):
            return meower.resp({"type": "noAuthenticationMethods"}, 400, error=True)

        # Check for required data
        meower.check_for_json([{"id": "password", "t": str, "l_min": 0, "l_max": 256}])

        # Check if TOTP is required and if it is valid
        if userdata["security"]["totp"] is not None:
            # Check for required data
            meower.check_for_json({"id": "totp", "t": str, "l_min": 6, "l_max": 6})

            # Check if it's valid
            if not (pyotp.TOTP(userdata["security"]["totp"]["secret"]).verify(request.json["totp"]) or (request.json["totp"] in userdata["security"]["totp"]["recovery_codes"])):
                return meower.resp({"type": "invalidCredentials", "message": "Invalid TOTP code"}, 401, error=True)

        # Extract old password for simplicity
        password = request.json["password"].strip()

        # Remove password
        meower.db.users.update_one({"_id": request.user._id}, {"$set": {"security.password": None}})

        # Render and send security alert email
        if userdata["security"]["email"] is None:
            email = None
        else:
            email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
        if email is not None:
            with open("apiv0/email_templates/alerts/password_removed.html", "r") as f:
                email_template = Template(f.read()).render({"username": userdata["username"]})
            Thread(target=meower.send_email, args=(email, userdata["username"], "Security Alert", email_template,), kwargs={"type": "text/html"}).start()

        # Return success
        return meower.resp("empty")

@settings.route("/totp", methods=["GET", "PATCH", "DELETE"])
def totp():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:settings:authentication")

    # Get user data
    userdata = meower.db.users.find_one({"_id": request.user._id})

    if request.method == "GET":
        # Return whether the account has TOTP enabled
        return meower.resp(200, {"totp": (userdata["security"]["totp"] is not None)})
    elif request.method == "PATCH":
        # Check if account already has TOTP
        if userdata["security"]["totp"] is not None:
            return meower.resp({"type": "totpAlreadyEnabled", "message": "TOTP is already enabled"}, 400, error=True)

        # Check for required data
        meower.check_for_json([{"id": "secret", "t": str, "l_min": 16, "l_max": 16}, {"id": "totp", "t": str, "l_min": 6, "l_max": 6}])

        # Extract secret and code for simplicity
        secret = request.json["secret"].strip()
        code = request.json["totp"].strip()

        # Verify code
        if not pyotp.TOTP(secret).verify(code):
            return meower.resp({"type": "invalidCredentials", "message": "Invalid TOTP code"}, 401, error=True)
        
        # Set new TOTP secret and recovery codes
        recovery_codes = []
        for i in range(8):
            recovery_codes.append(str("".join(secrets.choice(string.ascii_letters + string.digits) for i in range(8))).lower())
        meower.db.users.update_one({"_id": request.user._id}, {"$set": {"security.totp": {"secret": secret, "recovery_codes": recovery_codes}}})

        # Render and send security alert email
        if userdata["security"]["email"] is None:
            email = None
        else:
            email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
        if email is not None:
            with open("apiv0/email_templates/alerts/totp_added.html", "r") as f:
                email_template = Template(f.read()).render({"username": userdata["username"]})
            Thread(target=meower.send_email, args=(email, userdata["username"], "Security Alert", email_template,), kwargs={"type": "text/html"}).start()

        # Return success
        return meower.resp(200, {"recovery_codes": recovery_codes})
    elif request.method == "DELETE":
        # Check for required data
        meower.check_for_json({"id": "totp", "t": str, "l_min": 6, "l_max": 6})

        # Check if TOTP is required and if it is valid
        if userdata["security"]["totp"] is not None:
            # Check for required data
            meower.check_for_json({"id": "totp", "t": str, "l_min": 6, "l_max": 6})

            # Check if it's valid
            if not (pyotp.TOTP(userdata["security"]["totp"]["secret"]).verify(request.json["totp"]) or (request.json["totp"] in userdata["security"]["totp"]["recovery_codes"])):
                return meower.resp({"type": "invalidCredentials", "message": "Invalid TOTP code"}, 401, error=True)
        else:
            return meower.resp({"type": "totpNotEnabled", "message": "TOTP is not enabled"}, 400, error=True)

        # Remove TOTP
        meower.db.users.update_one({"_id": request.user._id}, {"$set": {"security.totp": None}})

        # Render and send security alert email
        if userdata["security"]["email"] is None:
            email = None
        else:
            email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
            with open("apiv0/email_templates/alerts/totp_removed.html", "r") as f:
                email_template = Template(f.read()).render({"username": userdata["username"]})
            Thread(target=meower.send_email, args=(email, userdata["username"], "Security Alert", email_template,), kwargs={"type": "text/html"}).start()

        # Return success
        return meower.resp("empty")

@settings.route("/export-data", methods=["POST"])
def export_data():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:settings:danger")

    # Make sure user has a verified email
    userdata = meower.db.users.find_one({"_id": request.user._id})
    if userdata["security"]["email"] is None:
        return meower.resp({"type": "emailNotVerified", "message": "Email is not verified"}, 400, error=True)

    # Start thread to export data
    Thread(target=meower.export_data, args=(request.user._id,)).start()

    # Return success
    return meower.resp("empty")

@settings.route("/delete-account", methods=["POST"])
def delete_account():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:settings:danger")

    # Get user's email address
    userdata = meower.db.users.find_one({"_id": request.user._id})
    if userdata["security"]["email"] is None:
        return meower.resp({"type": "emailNotVerified", "message": "Email is not verified"}, 400, error=True)
    else:
        email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])

    # Create confirmation session
    session = meower.create_session(0, request.user._id, str(secrets.token_urlsafe(32)), expires=3600, action="delete-account")

    # Send confirmation email
    with open("apiv0/email_templates/confirmations/account_deletion.html", "r") as f:
        email_template = Template(f.read()).render({"username": userdata["username"], "token": session["token"]})
    Thread(target=meower.send_email, args=(email, userdata["username"], "Delete your Meower account", email_template,), kwargs={"type": "text/html"}).start()

    # Return success
    return meower.resp("empty")

@settings.route("/config", methods=["GET", "PATCH"])
def get_config():
    if request.method == "GET":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="foundation:settings:read_config")

        # Get user data
        userdata = meower.db.users.find_one({"_id": request.user._id})

        # Return current config
        return meower.resp(200, {"username": userdata["username"], "config": userdata["config"], "profile": userdata["profile"]})
    elif request.method == "PATCH":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="foundation:settings:edit_config")

        # Get user data
        userdata = meower.db.users.find_one({"_id": request.user._id})

        # Update username
        if "username" in request.json:
            username = request.json["username"].strip()
            if not (type(username) == str):
                return meower.resp(422)
            elif len(username) > 20:
                return meower.resp(413)
            elif meower.db.users.find_one({"lower_username": username.lower()}) is not None:
                return meower.resp({"type": "usernameAlreadyExists", "message": "That username is already taken"}, 409, error=True)
            userdata["username"] = username
            userdata["lower_username"] = username.lower()

        # Update profile picture
        if "pfp" in request.json:
            if type(request.json["pfp"]) == dict:
                if ("type" in request.json["pfp"]) and (request.json["pfp"]["type"] in [0, 1]):
                    userdata["config"]["pfp"]["type"] = request.json["pfp"]["type"]
                if ("data" in request.json["pfp"]) and ((type(request.json["pfp"]["data"]) == int) or (type(request.json["pfp"]["data"]) == string)):
                    userdata["config"]["pfp"]["data"] = request.json["pfp"]["data"]

        # Update bio
        if "bio" in request.json:
            if (type(request.json["bio"]) == str) and (request.json["bio"] < 100):
                userdata["config"]["bio"] = request.json["bio"]

        # Update status
        if "status" in request.json:
            if request.json["status"] in [0, 1, 2, 3]:
                userdata["config"]["status"] = request.json["status"]

        # Update theme
        if "theme" in request.json:
            if request.json["theme"] in ["orange", "blue"]:
                userdata["config"]["theme"] = request.json["theme"]
        if "mode" in request.json:
            if type(request.json["mode"]) == bool:
                userdata["config"]["mode"] = request.json["mode"]

        # Update sound effects
        if "sfx" in request.json:
            if type(request.json["sfx"]) == bool:
                userdata["config"]["sfx"] = request.json["sfx"]

        # Update background music
        if "bgm" in request.json:
            if type(request.json["bgm"]) == dict:
                if ("enabled" in request.json["bgm"]) and (type(request.json["bgm"]) == bool):
                    userdata["config"]["bgm"]["enabled"] = request.json["bgm"]["enabled"]
                if ("type" in request.json["bgm"]) and (request.json["bgm"]["type"] in [0, 1]):
                    userdata["config"]["bgm"]["type"] = request.json["bgm"]["type"]
                if ("data" in request.json["bgm"]) and ((type(request.json["bgm"]["data"]) == int) or (type(request.json["bgm"]["data"]) == string)) and (len(str(request.json["bgm"]["data"])) <= 300):
                    userdata["config"]["bgm"]["data"] = request.json["bgm"]["data"]

        # Update config
        meower.db.users.update_one({"_id": request.user._id}, {"$set": {"username": userdata["username"], "lower_username": userdata["lower_username"], "config": userdata["config"], "profile": userdata["profile"]}})

        # Return new config
        return meower.resp(200, {"username": userdata["username"], "config": userdata["config"], "profile": userdata["profile"]})

@settings.route("/blocked", methods=["GET", "PUT", "DELETE"])
def blocked_users():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:settings:blocked")

    # Get user data
    userdata = meower.db.users.find_one({"_id": request.user._id})
    
    if request.method == "GET":
        # Convert blocked users
        payload_blocked = []
        for user_id in userdata["security"]["blocked"]:
            user = meower.User(meower, user_id=user_id)
            if user.raw is None:
                continue
            else:
                payload_blocked.append(user.profile)

        # Return blocked users
        return meower.resp(200, {"blocked": payload_blocked})
    elif request.method == "PUT":
        # Check for required data
        meower.check_for_json([{"id": "username", "t": str, "l_min": 1, "l_max": 20}])

        # Make sure user exists
        blocked_user = meower.User(meower, username=request.json["username"])
        if blocked_user.raw is None:
            return meower.resp({"type": "userDoesNotExist"}, 404, error=True)

        # Add user to blocked list
        if blocked_user._id not in userdata["security"]["blocked"]:
            userdata["security"]["blocked"].append(blocked_user._id)
            meower.db.users.update_one({"_id": request.user._id}, {"$set": {"security.blocked": userdata["security"]["blocked"]}})

        # Return payload
        return meower.resp("empty")
    elif request.method == "DELETE":
        # Check for required data
        meower.check_for_json([{"id": "username", "t": str, "l_min": 1, "l_max": 20}])

        # Make sure user exists
        blocked_user = meower.User(meower, username=request.json["username"])
        if blocked_user.raw is None:
            return meower.resp({"type": "userDoesNotExist"}, 404, error=True)

        # Remove user from blocked list
        if blocked_user._id in userdata["security"]["blocked"]:
            userdata["security"]["blocked"].remove(blocked_user._id)
            meower.db.users.update_one({"_id": request.user._id}, {"$set": {"security.blocked": userdata["security"]["blocked"]}})

        # Return payload
        return meower.resp("empty")
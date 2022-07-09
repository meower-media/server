from jinja2 import Template
from flask import Blueprint, request, abort
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
    userdata = meower.db["usersv0"].find_one({"_id": request.session.user})

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
    return meower.respond({"email": email, "password": password, "totp": totp, "webauthn": webauthn}, 200, error=False)

@settings.route("/email", methods=["GET", "PATCH"])
def email_address():
    # Get user data
    userdata = meower.db["usersv0"].find_one({"_id": request.session.user})

    if request.method == "GET":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="foundation:settings:read_email")

        # Get email address
        if userdata["security"]["email"] is None:
            email = None
        else:
            email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])

        # Return the email address
        return meower.respond(email, 200, error=False)
    elif request.method == "PATCH":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="foundation:settings:authentication")

        # Check for required data
        meower.check_for_json(["email"])

        # Extract email for simplicity
        email = request.json["email"].strip()

        # Check for bad datatypes and syntax
        if not (type(email) == str):
            return meower.respond({"type": "badDatatype"}, 400, error=True)
        elif len(email) > 100:
            return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
        elif not meower.is_valid_email(email):
            return meower.respond({"type": "badSyntax"}, 400, error=True)

        # Create email verification session
        encryption_id, encrypted_email = meower.encrypt(email)
        token = secrets.token_urlsafe(32)
        meower.create_session(0, request.session.user, token, email={"encryption_id": encryption_id, "encrypted_email": encrypted_email}, expires=3600, action="verify")

        # Render and send email
        with open("apiv0/email_templates/confirmations/email_verification.html", "r") as f:
            email_template = Template(f.read()).render({"username": userdata["username"], "token": token})
        Thread(target=meower.send_email, args=(email, userdata["username"], "Verify your email address", email_template,), kwargs={"type": "text/html"}).start()

@settings.route("/password", methods=["GET", "PATCH", "DELETE"])
def password():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:settings:authentication")

    # Get user data
    userdata = meower.db["usersv0"].find_one({"_id": request.session.user})

    if request.method == "GET":
        # Return whether the account has a password
        return meower.respond({"password": (userdata["security"]["password"] is not None)}, 200, error=False)
    elif request.method == "PATCH":
        # Check for required data
        meower.check_for_json(["new_password"])

        # Extract new password for simplicity
        new_password = request.json["new_password"].strip()

        # Check for bad datatypes and syntax
        if not (type(new_password) == str):
            return meower.respond({"type": "badDatatype"}, 400, error=True)
        elif len(new_password) > 100:
            return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

        # Check if account has a current password
        if userdata["security"]["password"] is not None:
            # Check for required data
            meower.check_for_json(["old_password"])

            # Extract old password for simplicity
            old_password = request.json["old_password"].strip()

            # Check for bad datatypes and syntax
            if not (type(old_password) == str):
                return meower.respond({"type": "badDatatype"}, 400, error=True)
            elif len(old_password) > 100:
                return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

            # Verify old password
            if not scrypt.verify(sha256(old_password.encode()).hexdigest(), userdata["security"]["password"]["hash"]):
                return meower.respond({"type": "invalidCredentials", "message": "Invalid password."}, 401, error=True)

        # Change password
        hashed_password = scrypt.hash(sha256(new_password.encode()).hexdigest())
        meower.db["usersv0"].update_one({"_id": request.session.user}, {"$set": {"security.password": {"hash_type": "scrypt", "hash": hashed_password}}})

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
        return meower.respond({}, 200, error=False)
    elif request.method == "DELETE":
        # Check if account is eligible for password removal
        if (userdata["security"]["email"] is None) and (len(userdata["security"]["webauthn"]) == 0):
            return meower.respond({"type": "noAuthenticationMethods"}, 400, error=True)

        # Check for required data
        meower.check_for_json(["password"])

        # Extract old password for simplicity
        password = request.json["password"].strip()

        # Check for bad datatypes and syntax
        if not (type(password) == str):
            return meower.respond({"type": "badDatatype"}, 400, error=True)
        elif len(password) > 100:
            return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

        # Verify old password
        if not scrypt.verify(sha256(password.encode()).hexdigest(), userdata["security"]["password"]["hash"]):
            return meower.respond({"type": "invalidCredentials", "message": "Invalid password."}, 401, error=True)

        # Remove password
        meower.db["usersv0"].update_one({"_id": request.session.user}, {"$set": {"security.password": None}})

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
        return meower.respond({}, 200, error=False)

@settings.route("/totp", methods=["GET", "PATCH", "DELETE"])
def totp():
    # Check whether the client is authenticated
    meower.require_auth([5], scope="foundation:settings:authentication")

    # Get user data
    userdata = meower.db["usersv0"].find_one({"_id": request.session.user})

    if request.method == "GET":
        # Return whether the account has TOTP enabled
        return meower.respond({"totp": (userdata["security"]["totp"] is not None)}, 200, error=False)
    elif request.method == "PATCH":
        # Check if account already has TOTP
        if userdata["security"]["totp"] is not None:
            return meower.respond({"type": "totpAlreadyEnabled", "message": "TOTP is already enabled"}, 400, error=True)

        # Check for required data
        meower.check_for_json(["secret", "code"])

        # Extract secret and code for simplicity
        secret = request.json["secret"].strip()
        code = request.json["code"].strip()

        # Check for bad datatypes and syntax
        if not ((type(secret) == str) and (type(code) == str)):
            return meower.respond({"type": "badDatatype"}, 400, error=True)
        elif (len(secret) > 16) or (len(code) > 6):
            return meower.respond({"type": "fieldTooLarge"}, 400, error=True)

        # Verify code
        if not pyotp.TOTP(secret).verify(code):
            return meower.respond({"type": "invalidCredentials", "message": "Invalid TOTP code"}, 401, error=True)
        
        # Set new TOTP secret and recovery codes
        recovery_codes = []
        for i in range(8):
            recovery_codes.append(str("".join(secrets.choice(string.ascii_letters + string.digits) for i in range(8))).lower())
        meower.db["usersv0"].update_one({"_id": request.session.user}, {"$set": {"security.totp": {"secret": secret, "recovery_codes": recovery_codes}}})

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
        return meower.respond({"recovery_codes": recovery_codes}, 200, error=False)
    elif request.method == "DELETE":
        # Check if account has TOTP
        if userdata["security"]["totp"] is None:
            return meower.respond({"type": "totpNotEnabled", "message": "TOTP is not enabled"}, 400, error=True)

        # Verify code
        if not (pyotp.TOTP(userdata["security"]["totp"]["secret"]).verify(request.json["code"]) or (request.json["code"] in userdata["security"]["totp"]["recovery_codes"])):
            return meower.respond({"type": "invalidCredentials", "message": "Invalid TOTP code"}, 401, error=True)

        # Remove TOTP
        meower.db["usersv0"].update_one({"_id": request.session.user}, {"$set": {"security.totp": None}})

        # Render and send security alert email
        if userdata["security"]["email"] is None:
            email = None
        else:
            email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
        if email is not None:
            with open("apiv0/email_templates/alerts/totp_removed.html", "r") as f:
                email_template = Template(f.read()).render({"username": userdata["username"]})
            Thread(target=meower.send_email, args=(email, userdata["username"], "Security Alert", email_template,), kwargs={"type": "text/html"}).start()

        # Return success
        return meower.respond({}, 200, error=False)

@settings.route("/config", methods=["GET", "PATCH"])
def get_config():
    if request.method == "GET":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="foundation:settings:read_config")

        # Get user data
        userdata = meower.db["usersv0"].find_one({"_id": request.session.user})

        # Return current config
        return meower.respond({"username": userdata["username"], "config": userdata["config"], "profile": userdata["profile"]}, 200, error=False)
    elif request.method == "PATCH":
        # Check whether the client is authenticated
        meower.require_auth([5], scope="foundation:settings:edit_config")

        # Get user data
        userdata = meower.db["usersv0"].find_one({"_id": request.session.user})

        # Update username
        if "username" in request.json:
            username = request.json["username"].strip()
            if not (type(username) == str):
                return meower.respond({"type": "badDatatype"}, 400, error=True)
            elif len(username) > 20:
                return meower.respond({"type": "fieldTooLarge"}, 400, error=True)
            elif meower.db["usersv0"].find_one({"lower_username": username.lower()}) is not None:
                return meower.respond({"type": "usernameAlreadyExists", "message": "That username is already taken"}, 409, error=True)
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
                if ("data" in request.json["bgm"]) and ((type(request.json["bgm"]["data"]) == int) or (type(request.json["bgm"]["data"]) == string)):
                    userdata["config"]["bgm"]["data"] = request.json["bgm"]["data"]

        # Update config
        meower.db["usersv0"].update_one({"_id": request.session.user}, {"$set": {"username": userdata["username"], "lower_username": userdata["lower_username"], "config": userdata["config"], "profile": userdata["profile"]}})

        # Return new config
        return meower.respond({"username": userdata["username"], "config": userdata["config"], "profile": userdata["profile"]}, 200, error=False)
import re, os, requests, pyotp, secrets, time
from pydantic import BaseModel
from quart import Blueprint, request, abort, current_app as app
from quart_schema import validate_request
from pydantic import Field
from typing import Optional
from base64 import urlsafe_b64encode
from hashlib import sha256
from threading import Thread

from database import db, rdb, blocked_ips, registration_blocked_ips
from sessions import AccSession, EmailTicket
import security

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")

class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=255)
    totp_code: Optional[str] = Field(default="", min_length=6, max_length=6)
    mfa_recovery_code: Optional[str] = Field(default="", min_length=10, max_length=10)
    captcha: Optional[str] = Field(default="", max_length=2000)

class RecoverAccountBody(BaseModel):
    email: str = Field(min_length=1, max_length=255, pattern=security.EMAIL_REGEX)
    captcha: Optional[str] = Field(default="", max_length=2000)


@auth_bp.before_request
async def ip_block_check():
    if blocked_ips.search_best(request.ip):
        return {"error": True, "type": "ipBlocked"}, 403


@auth_bp.post("/login")
@validate_request(AuthRequest)
async def login(data: AuthRequest):
    # Make sure IP isn't ratelimited
    if security.ratelimited(f"login:i:{request.ip}"):
        abort(429)
    security.ratelimit(f"login:i:{request.ip}", 50, 900)

    # Get basic account details
    account = db.usersv0.find_one({
        "email": data.username
    } if "@" in data.username else {
        "lower_username": data.username.lower()
    }, projection={
        "_id": 1,
        "flags": 1,
        "pswd": 1,
        "mfa_recovery_code": 1
    })
    if not account:
        abort(401)

    # Make sure account isn't deleted
    if account["flags"] & security.UserFlags.DELETED:
        return {"error": True, "type": "accountDeleted"}, 401

    # Make sure account isn't locked
    if account["flags"] & security.UserFlags.LOCKED:
        return {"error": True, "type": "accountLocked"}, 401

    # Make sure account isn't ratelimited
    if security.ratelimited(f"login:u:{account['_id']}"):
        abort(429)

    # Legacy tokens (remove in the future at some point)
    if len(data.password) == 86:
        encoded_token = urlsafe_b64encode(sha256(data.password.encode()).digest())
        username = rdb.get(encoded_token)
        if username and username.decode() == account["_id"]:
            data.password = AccSession.create(
                username.decode(),
                request.ip,
                request.headers.get("User-Agent")
            ).token
            rdb.delete(encoded_token)

    # Check credentials & get session
    try:  # token for already existing session
        session = AccSession.get_by_token(data.password)
        session.refresh(request.ip, request.headers.get("User-Agent"), check_token=data.password)
    except:  # no error capturing here, as it's probably just a password rather than a token, and we don't want to capture passwords
        # Check password
        password_valid = security.check_password_hash(data.password, account["pswd"])

        # Maybe they put their MFA credentials at the end of their password?
        if (not password_valid) and db.authenticators.count_documents({"user": account["_id"]}, limit=1):
            if (not data.mfa_recovery_code) and data.password.endswith(account["mfa_recovery_code"]):
                try:
                    data.mfa_recovery_code = data.password[-10:]
                    data.password = data.password[:-10]
                except: pass
                else:
                    password_valid = security.check_password_hash(data.password, account["pswd"])
            elif not data.totp_code:
                try:
                    data.totp_code = data.password[-6:]
                    data.password = data.password[:-6]
                except: pass
                else:
                    if re.fullmatch(security.TOTP_REGEX, data.totp_code):
                        password_valid = security.check_password_hash(data.password, account["pswd"])

        # Abort if password is invalid
        if not password_valid:
            security.ratelimit(f"login:u:{account['_id']}", 5, 60)
            security.log_security_action("auth_fail", account["_id"], {
                "status": "invalid_password",
                "ip": request.ip,
                "user_agent": request.headers.get("User-Agent")
            })
            abort(401)

        # Check MFA
        authenticators = list(db.authenticators.find({"user": account["_id"]}))
        if len(authenticators) > 0:
            if data.totp_code:
                passed = False
                for authenticator in authenticators:
                    if authenticator["type"] != "totp":
                        continue
                    if pyotp.TOTP(authenticator["totp_secret"]).verify(data.totp_code, valid_window=1):
                        passed = True
                        break
                if not passed:
                    security.ratelimit(f"login:u:{account['_id']}", 5, 60)
                    security.log_security_action("auth_fail", account["_id"], {
                        "status": "invalid_totp_code",
                        "ip": request.ip,
                        "user_agent": request.headers.get("User-Agent")
                    })
                    abort(401)
            elif data.mfa_recovery_code:
                if data.mfa_recovery_code == account["mfa_recovery_code"]:
                    db.authenticators.delete_many({"user": account["_id"]})

                    new_recovery_code = secrets.token_hex(5)
                    db.usersv0.update_one({"_id": account["_id"]}, {"$set": {
                        "mfa_recovery_code": new_recovery_code
                    }})
                    security.log_security_action("mfa_recovery_used", account["_id"], {
                        "old_recovery_code_hash": urlsafe_b64encode(sha256(data.mfa_recovery_code.encode()).digest()).decode(),
                        "new_recovery_code_hash": urlsafe_b64encode(sha256(new_recovery_code.encode()).digest()).decode(),
                        "ip": request.ip,
                        "user_agent": request.headers.get("User-Agent")
                    })
                else:
                    security.ratelimit(f"login:u:{account['_id']}", 5, 60)
                    security.log_security_action("auth_fail", account["_id"], {
                        "status": "invalid_recovery_code",
                        "ip": request.ip,
                        "user_agent": request.headers.get("User-Agent")
                    })
                    abort(401)
            else:
                mfa_methods = set()
                for authenticator in authenticators:
                    mfa_methods.add(authenticator["type"])
                security.log_security_action("auth_fail", account["_id"], {
                    "status": "mfa_required",
                    "ip": request.ip,
                    "user_agent": request.headers.get("User-Agent")
                })
                return {
                    "error": True,
                    "type": "mfaRequired",
                    "mfa_methods": list(mfa_methods)
                }, 401

        # Create session
        session = AccSession.create(account["_id"], request.ip, request.headers.get("User-Agent"))

    # Return session and account details
    return {
        "error": False,
        "session": session.v0,
        "token": session.token,
        "account": security.get_account(account['_id'], True)
    }, 200


@auth_bp.post("/register")
@validate_request(AuthRequest)
async def register(data: AuthRequest):
    # Make sure registration isn't disabled
    if not app.supporter.registration:
        return {"error": True, "type": "registrationDisabled"}, 403
    
    # Make sure IP isn't being ratelimited
    if security.ratelimited(f"register:{request.ip}:f") or security.ratelimited(f"register:{request.ip}:s"):
        abort(429)

    # Make sure password is between 8-72 characters
    if len(data.password) < 8 or len(data.password) > 72:
        abort(400)

    # Make sure username matches regex
    if not re.fullmatch(security.USERNAME_REGEX, data.username):
        abort(400)
    
    # Make sure IP isn't blocked from creating new accounts
    if registration_blocked_ips.search_best(request.ip):
        security.ratelimit(f"register:{request.ip}:f", 5, 30)
        return {"error": True, "type": "registrationBlocked"}, 403

    # Make sure username isn't taken
    if security.account_exists(data.username, ignore_case=True):
        security.ratelimit(f"register:{request.ip}:f", 5, 30)
        return {"error": True, "type": "usernameExists"}, 409

    # Check captcha
    if os.getenv("CAPTCHA_SECRET") and not (hasattr(request, "bypass_captcha") and request.bypass_captcha):
        if not requests.post("https://api.hcaptcha.com/siteverify", data={
            "secret": os.getenv("CAPTCHA_SECRET"),
            "response": data.captcha,
        }).json()["success"]:
            return {"error": True, "type": "invalidCaptcha"}, 403

    # Create account
    security.create_account(data.username, data.password, request.ip)

    # Ratelimit
    security.ratelimit(f"register:{request.ip}:s", 5, 900)
    
    # Create session
    session = AccSession.create(data.username, request.ip, request.headers.get("User-Agent"))

    # Return session and account details
    return {
        "error": False,
        "session": session.v0,
        "token": session.token,
        "account": security.get_account(data.username, True)
    }, 200


@auth_bp.post("/recover")
@validate_request(RecoverAccountBody)
async def recover_account(data: RecoverAccountBody):
    # Check ratelimits
    if security.ratelimited(f"recover:{request.ip}"):
        abort(429)
    security.ratelimit(f"recover:{request.ip}", 3, 2700)

    # Check captcha
    if os.getenv("CAPTCHA_SECRET") and not (hasattr(request, "bypass_captcha") and request.bypass_captcha):
        if not requests.post("https://api.hcaptcha.com/siteverify", data={
            "secret": os.getenv("CAPTCHA_SECRET"),
            "response": data.captcha,
        }).json()["success"]:
            return {"error": True, "type": "invalidCaptcha"}, 403

    # Get account
    account = db.usersv0.find_one({"email": data.email}, projection={"_id": 1, "email": 1, "flags": 1})
    if not account:
        return {"error": False}, 200

    # Create recovery email ticket
    ticket = EmailTicket(data.email, account["_id"], "recover", expires_at=int(time.time())+1800)

    # Send email
    txt_tmpl, html_tmpl = security.render_email_tmpl("recover", account["_id"], account["email"], {"token": ticket.token})
    Thread(
        target=security.send_email,
        args=[security.EMAIL_SUBJECTS["recover"], account["_id"], account["email"], txt_tmpl, html_tmpl]
    ).start()

    return {"error": False}, 200

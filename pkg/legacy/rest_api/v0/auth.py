import re, os, requests, time
from pydantic import BaseModel
from quart import Blueprint, request, abort, current_app as app
from quart_schema import validate_request
from pydantic import Field
from typing import Optional
from base64 import urlsafe_b64encode
from hashlib import sha256
from threading import Thread

from database import rdb, blocked_ips, registration_blocked_ips
from sessions import AccSession, EmailTicket
from users import UserFlags, User
from accounts import EMAIL_REGEX, TOTP_REGEX, Account
import errors, security

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")

class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=255)
    totp_code: Optional[str] = Field(default="", min_length=6, max_length=6)
    mfa_recovery_code: Optional[str] = Field(default="", min_length=10, max_length=10)
    captcha: Optional[str] = Field(default="", max_length=2000)

class RecoverAccountBody(BaseModel):
    email: str = Field(min_length=1, max_length=255, pattern=EMAIL_REGEX)
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

    # Get user and account
    try:
        if "@" in data.username:
            account = Account.get_by_email(data.username)
            user = User.get_by_id(account.id)
        else:
            user = User.get_by_username(data.username)
            account = user.account
    except errors.UserNotFound or errors.AccountNotFound:
        abort(401)

    # Make sure account isn't deleted
    if user.flags & UserFlags.DELETED:
        return {"error": True, "type": "accountDeleted"}, 401

    # Make sure account isn't locked
    if user.flags & UserFlags.LOCKED:
        return {"error": True, "type": "accountLocked"}, 401

    # Make sure account isn't ratelimited
    if security.ratelimited(f"login:u:{user.id}"):
        abort(429)

    # Legacy tokens (remove in the future at some point)
    if len(data.password) == 86:
        encoded_token = urlsafe_b64encode(sha256(data.password.encode()).digest())
        user_id = rdb.get(user_id)
        if user_id and int(user_id.decode()):
            data.password = AccSession.create(
                int(user_id.decode()),
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
        password_valid = account.check_password(data.password)

        # Maybe they put their MFA credentials at the end of their password?
        if (not password_valid) and len(account.mfa_methods):
            if (not data.mfa_recovery_code) and data.password.endswith(account["mfa_recovery_code"]):
                try:
                    data.mfa_recovery_code = data.password[-10:]
                    data.password = data.password[:-10]
                except: pass
                else:
                    password_valid = account.check_password(data.password)
            elif not data.totp_code:
                try:
                    data.totp_code = data.password[-6:]
                    data.password = data.password[:-6]
                except: pass
                else:
                    if re.fullmatch(TOTP_REGEX, data.totp_code):
                        password_valid = account.check_password(data.password)

        # Abort if password is invalid
        if not password_valid:
            security.ratelimit(f"login:u:{account.id}", 5, 60)
            await account.log_security_action("auth_fail", account.id, {
                "status": "invalid_password",
                "ip": request.ip,
                "user_agent": request.headers.get("User-Agent")
            })
            abort(401)

        # Check MFA
        if len(account.authenticators):
            if data.totp_code:
                if not account.check_totp_code(data.totp_code):
                    security.ratelimit(f"login:u:{account.id}", 5, 60)
                    await account.log_security_action("auth_fail", account.id, {
                        "status": "invalid_totp_code",
                        "ip": request.ip,
                        "user_agent": request.headers.get("User-Agent")
                    })
                    abort(401)
            elif data.mfa_recovery_code:
                if data.mfa_recovery_code != account.recovery_code:
                    security.ratelimit(f"login:u:{account.id}", 5, 60)
                    await account.log_security_action("auth_fail", account.id, {
                        "status": "invalid_recovery_code",
                        "ip": request.ip,
                        "user_agent": request.headers.get("User-Agent")
                    })
                    abort(401)

                account.reset_mfa()
                await account.log_security_action("mfa_recovery_used", account.id, {
                    "old_recovery_code_hash": urlsafe_b64encode(sha256(data.mfa_recovery_code.encode()).digest()).decode(),
                    "new_recovery_code_hash": urlsafe_b64encode(sha256(account.recovery_code.encode()).digest()).decode(),
                    "ip": request.ip,
                    "user_agent": request.headers.get("User-Agent")
                })
            else:
                await account.log_security_action("auth_fail", account.id, {
                    "status": "mfa_required",
                    "ip": request.ip,
                    "user_agent": request.headers.get("User-Agent")
                })
                return {
                    "error": True,
                    "type": "mfaRequired",
                    "mfa_methods": account.mfa_methods
                }, 401

        # Create session
        session = AccSession.create(account.id, request.ip, request.headers.get("User-Agent"))

    # Return session and account details
    return {
        "error": False,
        "session": session.v0,
        "token": session.token,
        "account": security.get_account(account.id, True)
    }, 200


@auth_bp.post("/register")
@validate_request(AuthRequest)
async def register(data: AuthRequest):
    # Make sure registration isn't disabled
    if not app.supporter.registration:
        return {"error": True, "type": "registrationDisabled"}, 403
    
    # Make sure IP isn't blocked from creating new accounts
    if registration_blocked_ips.search_best(request.ip):
        return {"error": True, "type": "registrationBlocked"}, 403

    # Make sure IP isn't being ratelimited
    if security.ratelimited(f"register:{request.ip}:f") or security.ratelimited(f"register:{request.ip}:s"):
        abort(429)
    
    # Check captcha
    if os.getenv("CAPTCHA_SECRET") and not (hasattr(request, "bypass_captcha") and request.bypass_captcha):
        if not requests.post("https://api.hcaptcha.com/siteverify", data={
            "secret": os.getenv("CAPTCHA_SECRET"),
            "response": data.captcha,
        }).json()["success"]:
            security.ratelimit(f"register:{request.ip}:f", 5, 30)
            return {"error": True, "type": "invalidCaptcha"}, 403

    # Create account
    try:
        account, user = await User.create_account(data.username, data.password)
    except errors.UsernameDisallowed or errors.PasswordDisallowed:
        security.ratelimit(f"register:{request.ip}:f", 5, 30)
        abort(400)
    except errors.UsernameTaken:
        security.ratelimit(f"register:{request.ip}:f", 5, 30)
        abort(409)
    else:
        # Ratelimit
        security.ratelimit(f"register:{request.ip}:s", 3, 900)

        # Create session
        session = AccSession.create(data.username, request.ip, request.headers.get("User-Agent"))

        # Return session and account details
        return {
            "error": False,
            "session": session.v0,
            "token": session.token,
            "account": {"email": account.email, **user.v0, **user.settings}
        }, 200


@auth_bp.post("/recover")
@validate_request(RecoverAccountBody)
async def recover_account(data: RecoverAccountBody):
    # Check ratelimits
    if security.ratelimited(f"recover:{request.ip}"):
        abort(429)
    security.ratelimit(f"recover:{request.ip}", 3, 900)

    # Check captcha
    if os.getenv("CAPTCHA_SECRET") and not (hasattr(request, "bypass_captcha") and request.bypass_captcha):
        if not requests.post("https://api.hcaptcha.com/siteverify", data={
            "secret": os.getenv("CAPTCHA_SECRET"),
            "response": data.captcha,
        }).json()["success"]:
            return {"error": True, "type": "invalidCaptcha"}, 403

    # Get account
    try:
        account = Account.get_by_email(data.email)
    except errors.AccountNotFound: pass
    else:
        # Create recovery email ticket
        ticket = EmailTicket(account.email, account.id, "recover", expires_at=int(time.time())+1800)

        # Send email
        txt_tmpl, html_tmpl = security.render_email_tmpl("recover", account.id, account.email, {"token": ticket.token})
        Thread(
            target=security.send_email,
            args=[security.EMAIL_SUBJECTS["recover"], account.id, account.email, txt_tmpl, html_tmpl]
        ).start()
    finally:
        return {"error": False}, 200

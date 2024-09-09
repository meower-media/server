from typing import Optional, Any, Literal
from hashlib import sha256
from base64 import urlsafe_b64encode, urlsafe_b64decode
from threading import Thread
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import time, requests, os, uuid, secrets, bcrypt, hmac, msgpack, jinja2, smtplib, re

from database import db, rdb, signing_keys
from utils import log
from uploads import clear_files
import errors

"""
Meower Security Module
This module provides account management and authentication services.
"""

SENSITIVE_ACCOUNT_FIELDS = {
    "normalized_email_hash",
    "pswd",
    "mfa_recovery_code",
    "delete_after"
}

SENSITIVE_ACCOUNT_FIELDS_DB_PROJECTION = {}
for key in SENSITIVE_ACCOUNT_FIELDS:
    SENSITIVE_ACCOUNT_FIELDS_DB_PROJECTION[key] = 0

SYSTEM_USER_USERNAMES = {"server", "deleted", "meower", "admin", "username"}
SYSTEM_USER = {}

DEFAULT_USER_SETTINGS = {
    "unread_inbox": True,
    "theme": "orange",
    "mode": True,
    "layout": "new",
    "sfx": True,
    "bgm": False,
    "bgm_song": 2,
    "debug": False,
    "hide_blocked_users": False,
    "active_dms": [],
    "favorited_chats": []
}


USERNAME_REGEX = "[a-zA-Z0-9-_]{1,20}"
# I hate this. But, thanks https://stackoverflow.com/a/201378
EMAIL_REGEX = r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"""
TOTP_REGEX = "[0-9]{6}"
BCRYPT_SALT_ROUNDS = 14
TOKEN_BYTES = 64


TOKEN_TYPES = Literal[
    "acc",   # account authorization
    "email", # email actions (such as email verification or account recovery)
]


EMAIL_SUBJECTS = {
    "verify": "Verify your email address",
    "recover": "Reset your password",
    "security_alert": "Security alert",
    "locked": "Your account has been locked"
}


email_file_loader = jinja2.FileSystemLoader("email_templates")
email_env = jinja2.Environment(loader=email_file_loader)


class UserFlags:
    SYSTEM = 1
    DELETED = 2
    PROTECTED = 4
    POST_RATELIMIT_BYPASS = 8
    REQUIRE_EMAIL = 16  # not used yet
    LOCKED = 32


class AdminPermissions:
    SYSADMIN = 1

    VIEW_REPORTS = 2
    EDIT_REPORTS = 4

    VIEW_NOTES = 8
    EDIT_NOTES = 16

    VIEW_POSTS = 32
    DELETE_POSTS = 64

    VIEW_ALTS = 128
    SEND_ALERTS = 256
    KICK_USERS = 512
    CLEAR_PROFILE_DETAILS = 1024
    VIEW_BAN_STATES = 2048
    EDIT_BAN_STATES = 4096
    DELETE_USERS = 8192

    VIEW_IPS = 16384
    BLOCK_IPS = 32768

    VIEW_CHATS = 65536
    EDIT_CHATS = 131072

    SEND_ANNOUNCEMENTS = 262144


class Restrictions:
    HOME_POSTS = 1
    CHAT_POSTS = 2
    NEW_CHATS = 4
    EDITING_CHAT_DETAILS = 8
    EDITING_PROFILE = 16


def ratelimited(bucket_id: str):
    remaining = rdb.get(f"rtl:{bucket_id}")
    if remaining is not None and int(remaining.decode()) < 1:
        return True
    else:
        return False


def ratelimit(bucket_id: str, limit: int, seconds: int):
    remaining = rdb.get(f"rtl:{bucket_id}")
    if remaining is None:
        remaining = limit
    else:
        remaining = int(remaining.decode())

    expires = rdb.ttl(f"rtl:{bucket_id}")
    if expires <= 0:
        expires = seconds

    remaining -= 1
    rdb.set(f"rtl:{bucket_id}", remaining, ex=expires)


def clear_ratelimit(bucket_id: str):
    rdb.delete(f"rtl:{bucket_id}")


def account_exists(username, ignore_case=False):
    if not isinstance(username, str):
        log(f"Error on account_exists: Expected str for username, got {type(username)}")
        return False

    if (ignore_case or username == username.lower()) and username.lower() in SYSTEM_USER_USERNAMES:
        return True
    
    query = ({"lower_username": username.lower()} if ignore_case else {"_id": username})
    return (db.usersv0.count_documents(query, limit=1) > 0)


def create_account(username: str, password: str, ip: str):
    # Create user
    db.usersv0.insert_one({
        "_id": username,
        "lower_username": username.lower(),
        "uuid": str(uuid.uuid4()),
        "created": int(time.time()),
        "pfp_data": 1,
        "avatar": "",
        "avatar_color": "000000",
        "quote": "",
        "email": "",
        "normalized_email_hash": "",
        "pswd": hash_password(password),
        "mfa_recovery_code": secrets.token_hex(5),
        "flags": 0,
        "permissions": 0,
        "ban": {
            "state": "none",
            "restrictions": 0,
            "expires": 0,
            "reason": ""
        },
        "last_seen": int(time.time()),
        "delete_after": None
    })
    db.user_settings.insert_one({"_id": username})

    # Send welcome message
    rdb.publish("admin", msgpack.packb({
        "op": "alert_user",
        "user": username,
        "content": "Welcome to Meower! We welcome you with open arms! You can get started by making friends in the global chat or home, or by searching for people and adding them to a group chat. We hope you have fun!"
    }))

    # Automatically report if VPN is detected
    if get_ip_info(ip)["vpn"]:
        db.reports.insert_one({
            "_id": str(uuid.uuid4()),
            "type": "user",
            "content_id": username,
            "status": "pending",
            "escalated": False,
            "reports": [{
                "user": "Server",
                "ip": ip,
                "reason": f"User registered while using a VPN ({ip}).",
                "comment": "",
                "time": int(time())
            }]
        })


def get_account(username, include_config=False):
    # Check datatype
    if not isinstance(username, str):
        log(f"Error on get_account: Expected str for username, got {type(username)}")
        return None

    # System users
    if username.lower() in SYSTEM_USER_USERNAMES:
        return {
            "_id": username.title(),
            "lower_username": username.lower(),
            "uuid": None,
            "created": None,
            "pfp_data": None,
            "avatar": None,
            "avatar_color": None,
            "quote": None,
            "email": None,
            "flags": 1,
            "permissions": None,
            "ban": None,
            "last_seen": None
        }

    # Get account
    account = db.usersv0.find_one({"lower_username": username.lower()}, projection=SENSITIVE_ACCOUNT_FIELDS_DB_PROJECTION)
    if not account:
        return None

    # Make sure there's nothing sensitive on the account obj
    for key in SENSITIVE_ACCOUNT_FIELDS:
        if key in account:
            del account[key]

    # Add lvl and banned
    account["lvl"] = 0
    if account["ban"]:
        if account["ban"]["state"] == "perm_ban":
            account["banned"] = True
        elif (account["ban"]["state"] == "temp_ban") and (account["ban"]["expires"] > time.time()):
            account["banned"] = True
        else:
            account["banned"] = False
    else:
        account["banned"] = False

    # Include config
    if include_config:
        account.update(DEFAULT_USER_SETTINGS)
        user_settings = db.user_settings.find_one({"_id": account["_id"]})
        if user_settings:
            del user_settings["_id"]
            account.update(user_settings)
    else:
        # Remove email and ban if not including config
        del account["email"]
        del account["ban"]

    return account


def create_token(ttype: TOKEN_TYPES, claims: Any) -> str:
    # Encode claims
    encoded_claims = msgpack.packb(claims)

    # Sign encoded claims
    signature = hmac.digest(signing_keys[ttype], encoded_claims, digest=sha256)

    # Construct token
    token = b".".join([urlsafe_b64encode(encoded_claims), urlsafe_b64encode(signature)])

    return token.decode()


def extract_token(token: str, expected_type: TOKEN_TYPES) -> Optional[Any]:
    # Extract data and signature
    encoded_claims, signature = token.split(".")
    encoded_claims = urlsafe_b64decode(encoded_claims)
    signature = urlsafe_b64decode(signature)

    # Check signature
    expected_signature = hmac.digest(signing_keys[expected_type], encoded_claims, digest=sha256)
    if not hmac.compare_digest(signature, expected_signature):
        raise errors.InvalidTokenSignature

    # Decode claims
    claims = msgpack.unpackb(encoded_claims)
    
    return claims


def update_settings(username, newdata):
    # Check datatype
    if not isinstance(username, str):
        log(f"Error on update_settings: Expected str for username, got {type(username)}")
        return False
    elif not isinstance(newdata, dict):
        log(f"Error on update_settings: Expected str for newdata, got {type(newdata)}")
        return False
    
    # Get user UUID and avatar
    account = db.usersv0.find_one({"lower_username": username.lower()}, projection={"_id": 1, "uuid": 1, "avatar": 1})
    if not account:
        return False
    
    # Init vars
    updated_user_vals = {}
    updated_user_settings_vals = {}

    # Update pfp
    if "pfp_data" in newdata and isinstance(newdata["pfp_data"], int):
        updated_user_vals["pfp_data"] = newdata["pfp_data"]
    if "avatar" in newdata and isinstance(newdata["avatar"], str) and len(newdata["avatar"]) <= 24:
        updated_user_vals["avatar"] = newdata["avatar"]
    if "avatar_color" in newdata and isinstance(newdata["avatar_color"], str) and len(newdata["avatar_color"]) == 6:
        updated_user_vals["avatar_color"] = newdata["avatar_color"]
    
    # Update quote
    if "quote" in newdata and isinstance(newdata["quote"], str) and len(newdata["quote"]) <= 360:
        updated_user_vals["quote"] = newdata["quote"]

    # Update settings
    for key, default_val in DEFAULT_USER_SETTINGS.items():
        if key in newdata:
            if isinstance(newdata[key], type(default_val)):
                if key == "favorited_chats" and len(newdata[key]) > 50:
                    newdata[key] = newdata[key][:50]
                
                updated_user_settings_vals[key] = newdata[key]

    # Update database items
    if len(updated_user_vals) > 0:
        db.usersv0.update_one({"_id": account["_id"]}, {"$set": updated_user_vals})
    if len(updated_user_settings_vals) > 0:
        db.user_settings.update_one({"_id": account["_id"]}, {"$set": updated_user_settings_vals}, upsert=True)

    return True


def get_permissions(username):
    if not isinstance(username, str):
        log(f"Error on get_permissions: Expected str for username, got {type(username)}")
        return 0

    account = db.usersv0.find_one({"lower_username": username.lower()}, projection={"permissions": 1})
    if account:
        return account["permissions"]
    else:
        return 0


def has_permission(user_permissions, permission):
    if ((user_permissions & AdminPermissions.SYSADMIN) == AdminPermissions.SYSADMIN):
        return True
    else:
        return ((user_permissions & permission) == permission)


def is_restricted(username, restriction):
    # Check datatypes
    if not isinstance(username, str):
        log(f"Error on is_restricted: Expected str for username, got {type(username)}")
        return False
    elif not isinstance(restriction, int):
        log(f"Error on is_restricted: Expected int for username, got {type(restriction)}")
        return False

    # Get account
    account = db.usersv0.find_one({"lower_username": username.lower()}, projection={"ban.state": 1, "ban.restrictions": 1, "ban.expires": 1})
    if not account:
        return False
    
    # Check type
    if account["ban"]["state"] == "none":
        return False
    
    # Check expiration
    if "perm" not in account["ban"]["state"] and account["ban"]["expires"] < int(time.time()):
        return False
    
    # Return whether feature is restricted
    return (account["ban"]["restrictions"] & restriction) == restriction


def delete_account(username, purge=False):
    # Get account
    account = db.usersv0.find_one({"_id": username}, projection={"uuid": 1, "flags": 1})
    if not account:
        return

    # Add deleted flag
    account["flags"] |= UserFlags.DELETED

    # Update account
    db.usersv0.update_one({"_id": username}, {"$set": {
        "pfp_data": None,
        "avatar": None,
        "avatar_color": None,
        "quote": None,
        "email": None,
        "normalized_email_hash": None,
        "pswd": None,
        "mfa_recovery_code": None,
        "flags": account["flags"],
        "permissions": None,
        "ban": None,
        "last_seen": None,
        "delete_after": None
    }})

    # Delete pending email
    rdb.delete(f"pe{username}")

    # Delete authenticators
    db.authenticators.delete_many({"user": username})

    # Delete sessions
    db.acc_sessions.delete_many({"user": username})

    # Delete security logs
    db.security_log.delete_many({"user": username})

    # Delete uploaded files
    clear_files(username)

    # Delete user settings
    db.user_settings.delete_one({"_id": username})

    # Remove from reports
    db.reports.update_many({"reports.user": username}, {"$pull": {
        "reports": {"user": username}
    }})

    # Delete relationships
    db.relationships.delete_many({"$or": [
        {"_id.from": username},
        {"_id.to": username}
    ]})

    # Update or delete chats
    for chat in db.chats.find({
        "members": username
    }, projection={"type": 1, "owner": 1, "members": 1}):
        if chat["type"] == 1 or len(chat["members"]) == 1:
            db.posts.delete_many({"post_origin": chat["_id"], "isDeleted": False})
            db.chats.delete_one({"_id": chat["_id"]})
        else:
            if chat["owner"] == username:
                chat["owner"] = "Deleted"
            chat["members"].remove(username)
            db.chats.update_one({"_id": chat["_id"]}, {"$set": {
                "owner": chat["owner"],
                "members": chat["members"]
            }})

    # Delete posts
    db.posts.delete_many({"u": username})

    # Purge user
    if purge:
        db.reports.delete_many({"content_id": username, "type": "user"})
        db.admin_notes.delete_one({"_id": account["uuid"]})
        db.usersv0.delete_one({"_id": username})


def get_ip_info(ip_address):
    # Get IP hash
    ip_hash = urlsafe_b64encode(sha256(ip_address.encode()).digest()).decode()

    # Get from cache
    ip_info = rdb.get(f"ip{ip_hash}")
    if ip_info:
        return msgpack.unpackb(ip_info)
    
    # Get from IP-API
    resp = requests.get(f"http://ip-api.com/json/{ip_address}?fields=25349915")
    if resp.ok and resp.json()["status"] == "success":
        resp_json = resp.json()
        ip_info = {
            "country_code": resp_json["countryCode"],
            "country_name": resp_json["country"],
            "region": resp_json["regionName"],
            "city": resp_json["city"],
            "timezone": resp_json["timezone"],
            "currency": resp_json["currency"],
            "as": resp_json["as"],
            "isp": resp_json["isp"],
            "vpn": (resp_json.get("hosting") or resp_json.get("proxy"))
        }
        rdb.set(f"ip{ip_hash}", msgpack.packb(ip_info), ex=int(time.time())+(86400*21))  # cache for 3 weeks
        return ip_info
    
    # Fallback
    return {
        "country_code": "Unknown",
        "country_name": "Unknown",
        "region": "Unknown",
        "city": "Unknown",
        "timezone": "Unknown",
        "currency": "Unknown",
        "as": "Unknown",
        "isp": "Unknown",
        "vpn": False
    }


def log_security_action(action_type: str, user: str, data: dict):
    db.security_log.insert_one({
        "_id": str(uuid.uuid4()),
        "type": action_type,
        "user": user,
        "time": int(time.time()),
        "data": data
    })

    if action_type in {
        "email_changed",
        "password_changed",
        "mfa_added",
        "mfa_removed",
        "mfa_recovery_reset",
        "mfa_recovery_used",
        "locked"
    }:
        tmpl_name = "locked" if action_type == "locked" else "security_alert"
        platform_name = os.environ["EMAIL_PLATFORM_NAME"]

        account = db.usersv0.find_one({"_id": user}, projection={"_id": 1, "email": 1})

        txt_tmpl, html_tmpl = render_email_tmpl(tmpl_name, account["_id"], account.get("email", ""), {
            "msg": {
                "email_changed": f"The email address on your {platform_name} account has been changed.",
                "password_changed": f"The password on your {platform_name} account has been changed.",
                "mfa_added": f"A multi-factor authenticator has been added to your {platform_name} account.",
                "mfa_removed": f"A multi-factor authenticator has been removed from your {platform_name} account.",
                "mfa_recovery_reset": f"The multi-factor authentication recovery code on your {platform_name} account has been reset.",
                "mfa_recovery_used": f"Your multi-factor authentication recovery code has been used to reset multi-factor authentication on your {platform_name} account."
            }[action_type] if action_type != "locked" else None,
            "token": create_token("email", [  # this doesn't use EmailTicket in sessions.py because it'd be a recursive import
                account["email"],
                account["_id"],
                "lockdown",
                int(time.time())+86400
            ]) if account.get("email") and action_type != "locked" else None
        })
    
        # Email
        if account.get('email'):
            Thread(
                target=send_email,
                args=[EMAIL_SUBJECTS[tmpl_name], account["_id"], account["email"], txt_tmpl, html_tmpl]
            ).start()

        # Inbox
        rdb.publish("admin", msgpack.packb({
            "op": "alert_user",
            "user": account["_id"],
            "content": txt_tmpl
        }))


def add_audit_log(action_type, mod_username, mod_ip, data):
    db.audit_log.insert_one({
        "_id": str(uuid.uuid4()),
        "type": action_type,
        "mod_username": mod_username,
        "mod_ip": mod_ip,
        "time": int(time.time()),
        "data": data
    })


def background_tasks_loop():
    while True:
        time.sleep(1800)  # Once every 30 minutes

        log("Running background tasks...")

        # Delete accounts scheduled for deletion
        for user in db.usersv0.find({"delete_after": {"$lt": int(time.time())}}, projection={"_id": 1}):
            try:
                delete_account(user["_id"])
            except Exception as e:
                log(f"Failed to delete account {user['_id']}: {e}")

        # Revoke inactive sessions (3 weeks of inactivity)
        db.acc_sessions.delete_many({"refreshed_at": {"$lt": int(time.time())-(86400*21)}})

        # Purge old deleted posts
        db.posts.delete_many({"deleted_at": {"$lt": int(time.time())-2419200}})

        # Purge old post revisions
        db.post_revisions.delete_many({"time": {"$lt": int(time.time())-2419200}})

        """ we should probably not be getting rid of audit logs...
        # Purge old "get" admin audit logs
        db.audit_log.delete_many({
            "time": {"$lt": int(time.time())-2419200},
            "type": {"$in": [
                "got_reports",
                "got_report",
                "got_notes",
                "got_users",
                "got_user",
                "got_user_posts",
                "got_chat",
                "got_netinfo",
                "got_netblocks",
                "got_netblock",
                "got_announcements"
            ]}
        })
        """

        log("Finished background tasks!")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_SALT_ROUNDS)).decode()


def check_password_hash(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


def get_normalized_email_hash(address: str) -> str:
    """
    Get a hash of an email address with aliases and dots stripped.
    This is to allow using address aliases, but to still detect ban evasion.
    Also, Gmail ignores dots in addresses. Thanks Google.
    """

    identifier, domain = address.split("@")
    identifier = re.split(r'\+|\%', identifier)[0]
    identifier = identifier.replace(".", "")

    return urlsafe_b64encode(sha256(f"{identifier}@{domain}".encode()).digest()).decode()


def render_email_tmpl(template: str, to_name: str, to_address: str, data: Optional[dict[str, str]] = {}) -> tuple[str, str]:
    data.update({
        "subject": EMAIL_SUBJECTS[template],
        "name": to_name,
        "address": to_address,
        "env": os.environ
    })
    
    txt_tmpl = email_env.get_template(f"{template}.txt")
    html_tmpl = email_env.get_template(f"{template}.html")

    return txt_tmpl.render(data), html_tmpl.render(data)


def send_email(subject: str, to_name: str, to_address: str, txt_tmpl: str, html_tmpl: str):
    message = MIMEMultipart("alternative")
    message["From"] = formataddr((os.environ["EMAIL_FROM_NAME"], os.environ["EMAIL_FROM_ADDRESS"]))
    message["To"] = formataddr((to_name, to_address))
    message["Subject"] = subject
    message.attach(MIMEText(txt_tmpl, "plain"))
    message.attach(MIMEText(html_tmpl, "html"))

    with smtplib.SMTP(os.environ["EMAIL_SMTP_HOST"], int(os.environ["EMAIL_SMTP_PORT"])) as server:
        if os.getenv("EMAIL_SMTP_TLS"):
            server.starttls()
        server.login(os.environ["EMAIL_SMTP_USERNAME"], os.environ["EMAIL_SMTP_PASSWORD"])
        server.sendmail(os.environ["EMAIL_FROM_ADDRESS"], to_address, message.as_string())

from quart import Blueprint, current_app as app, request, abort
from quart_schema import validate_request, validate_querystring
from pydantic import BaseModel, Field
from typing import Optional, List
from copy import copy
from threading import Thread
import pymongo
import uuid
import time
import uuid
import os
import requests

import security
from database import db, rdb, get_total_pages
from accounts import EMAIL_REGEX
from uploads import claim_file, delete_file
from sessions import AccSession, EmailTicket
from utils import log


me_bp = Blueprint("me_bp", __name__, url_prefix="/me")


class DeleteAccountBody(BaseModel):
    password: str = Field(min_length=1, max_length=255)  # change in API v1

class UpdateConfigBody(BaseModel):
    pfp_data: Optional[int] = Field(default=None)
    avatar: Optional[str] = Field(default=None, max_length=24)
    avatar_color: Optional[str] = Field(default=None, min_length=6, max_length=6)  # hex code without the #
    quote: Optional[str] = Field(default=None, max_length=360)

    unread_inbox: Optional[bool] = Field(default=None)
    
    theme: Optional[str] = Field(default=None, min_length=1, max_length=256)
    mode: Optional[bool] = Field(default=None)
    layout: Optional[str] = Field(default=None, min_length=1, max_length=256)
    sfx: Optional[bool] = Field(default=None)
    bgm: Optional[bool] = Field(default=None)
    bgm_song: Optional[int] = Field(default=None)
    debug: Optional[bool] = Field(default=None)
    hide_blocked_users: Optional[bool] = Field(default=None)
    
    favorited_chats: Optional[List[str]] = Field(default=None)

    class Config:
        validate_assignment = True
        str_strip_whitespace = True

class UpdateEmailBody(BaseModel):
    password: str = Field(min_length=1, max_length=255)  # change in API v1
    email: str = Field(max_length=255, pattern=EMAIL_REGEX)
    captcha: Optional[str] = Field(default="", max_length=2000)

class RemoveEmailBody(BaseModel):
    password: str = Field(min_length=1, max_length=255)  # change in API v1

class GetReportsQueryArgs(BaseModel):
    page: Optional[int] = Field(default=1, ge=1)


@me_bp.get("/")
async def get_me():
    # Check authorization
    if not request.user:
        abort(401)

    # Update last_seen (this is only to remove CL3's dependency on the DB)
    db.usersv0.update_one({"_id": request.user}, {"$set": {"last_seen": int(time.time())}})

    # Get and return account
    return {"error": False, **security.get_account(request.user, include_config=True)}, 200


@me_bp.delete("/")
@validate_request(DeleteAccountBody)
async def delete_account(data: DeleteAccountBody):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"login:u:{request.user}"):
        abort(429)

    # Check password
    account = db.usersv0.find_one({"_id": request.user}, projection={"pswd": 1})
    if not security.check_password_hash(data.password, account["pswd"]):
        security.ratelimit(f"login:u:{request.user}", 5, 60)
        return {"error": True, "type": "invalidCredentials"}, 401
    
    # Schedule account for deletion
    db.usersv0.update_one({"_id": request.user}, {"$set": {
        "delete_after": int(time.time())+604800  # 7 days
    }})

    # Revoke sessions
    for session in AccSession.get_all(request.user):
        session.revoke()

    return {"error": False}, 200


@me_bp.patch("/config")
@validate_request(UpdateConfigBody)
async def update_config(data: UpdateConfigBody):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"config:{request.user}"):
        abort(429)
    
    # Ratelimit
    security.ratelimit(f"config:{request.user}", 10, 5)

    # Get new config
    new_config = data.model_dump()

    # Filter values that are set to None
    for k, v in copy(new_config).items():
        if v is None:
            del new_config[k]

    # Delete updated profile data if account is restricted
    if security.is_restricted(request.user, security.Restrictions.EDITING_PROFILE):
        if "pfp_data" in new_config:
            del new_config["pfp_data"]
        if "avatar" in new_config:
            del new_config["avatar"]
        if "avatar_color" in new_config:
            del new_config["avatar_color"]
        if "quote" in new_config:
            del new_config["quote"]

    # Claim avatar (and delete old one)
    if "avatar" in new_config:
        cur_avatar = db.usersv0.find_one({"_id": request.user}, projection={"avatar": 1})["avatar"]
        if new_config["avatar"] != "":
            try:
                claim_file(new_config["avatar"], "icons")
            except Exception as e:
                log(f"Unable to claim avatar: {e}")
                return {"error": True, "type": "unableToClaimAvatar"}, 500
        if cur_avatar:
            try:
                delete_file(cur_avatar)
            except Exception as e:
                log(f"Unable to delete avatar: {e}")

    # Update config
    security.update_settings(request.user, new_config)

    # Sync config between sessions
    app.cl.send_event("update_config", new_config, usernames=[request.user])

    # Send updated pfp and quote to other clients
    updated_profile_data = {"_id": request.user}
    if "pfp_data" in new_config:
        updated_profile_data["pfp_data"] = new_config["pfp_data"]
    if "avatar" in new_config:
        updated_profile_data["avatar"] = new_config["avatar"]
    if "avatar_color" in new_config:
        updated_profile_data["avatar_color"] = new_config["avatar_color"]
    if "quote" in new_config:
        updated_profile_data["quote"] = new_config["quote"]
    if len(updated_profile_data) > 1:
        app.cl.send_event("update_profile", updated_profile_data)

    return {"error": False}, 200


@me_bp.patch("/email")
@validate_request(UpdateEmailBody)
async def update_email(data: UpdateEmailBody):
    # Make sure email is enabled
    if not os.getenv("EMAIL_SMTP_HOST"):
        return {"error": True, "type": "featureDisabled"}, 503

    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimits
    if security.ratelimited(f"login:u:{request.user}") or security.ratelimited(f"emailch:{request.user}"):
        abort(429)

    # Check password
    account = db.usersv0.find_one({"_id": request.user}, projection={"pswd": 1})
    if not security.check_password_hash(data.password, account["pswd"]):
        security.ratelimit(f"login:u:{request.user}", 5, 60)
        return {"error": True, "type": "invalidCredentials"}, 401

    # Make sure the email address hasn't been used before
    if db.usersv0.count_documents({"normalized_email_hash": security.get_normalized_email_hash(data.email)}, limit=1):
        return {"error": True, "type": "emailExists"}, 409

    # Ratelimit
    security.ratelimit(f"emailch:{request.user}", 3, 2700)

    # Check captcha
    if os.getenv("CAPTCHA_SECRET") and not (hasattr(request, "bypass_captcha") and request.bypass_captcha):
        if not requests.post("https://api.hcaptcha.com/siteverify", data={
            "secret": os.getenv("CAPTCHA_SECRET"),
            "response": data.captcha,
        }).json()["success"]:
            return {"error": True, "type": "invalidCaptcha"}, 403

    # Create email verification ticket
    ticket = EmailTicket(data.email, request.user, "verify", expires_at=int(time.time())+1800)

    # Set pending email address
    rdb.set(f"pe{request.user}", data.email, ex=1800)

    # Send email
    txt_tmpl, html_tmpl = security.render_email_tmpl("verify", request.user, data.email, {"token": ticket.token})
    Thread(
        target=security.send_email,
        args=[security.EMAIL_SUBJECTS["verify"], request.user, data.email, txt_tmpl, html_tmpl]
    ).start()

    return {"error": False}, 200


@me_bp.delete("/email")
@validate_request(RemoveEmailBody)
async def remove_email(data: RemoveEmailBody):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimits
    if security.ratelimited(f"login:u:{request.user}"):
        abort(429)

    # Check password
    account = db.usersv0.find_one({"_id": request.user}, projection={"email": 1, "pswd": 1})
    if not security.check_password_hash(data.password, account["pswd"]):
        security.ratelimit(f"login:u:{request.user}", 5, 60)
        return {"error": True, "type": "invalidCredentials"}, 401

    # Log action
    security.log_security_action("email_changed", account["_id"], {
        "old_email_hash": security.get_normalized_email_hash(account["email"]) if account.get("email") else None,
        "new_email_hash": None,
        "ip": request.ip,
        "user_agent": request.headers.get("User-Agent")
    })

    # Update user's email address
    db.usersv0.update_one({"_id": account["_id"]}, {"$set": {
        "email": "",
        "normalized_email_hash": ""
    }})
    app.cl.send_event("update_config", {"email": ""}, usernames=[account["_id"]])

    return {"error": False}, 200


@me_bp.delete("/tokens")
async def delete_tokens():
    # Check authorization
    if not request.user:
        abort(401)
    
    # Revoke sessions
    for session in AccSession.get_all(request.user):
        session.revoke()

    return {"error": False}, 200


@me_bp.get("/reports")
@validate_querystring(GetReportsQueryArgs)
async def get_report_history(query_args: GetReportsQueryArgs):
    # Check authorization
    if not request.user:
        abort(401)

    # Get reports
    reports = list(
        db.reports.find(
            {"reports.user": request.user},
            projection={"escalated": 0},
            sort=[("reports.time", pymongo.DESCENDING)],
            skip=(query_args.page - 1) * 25,
            limit=25,
        )
    )

    # Get reason, comment, and time
    for report in reports:
        for _report in report["reports"]:
            if _report["user"] == request.user:
                report.update({
                    "reason": _report["reason"],
                    "comment": _report["comment"],
                    "time": _report["time"]
                })
        del report["reports"]

    # Get content
    for report in reports:
        if report["type"] == "post":
            report["content"] = db.posts.find_one(
                {"_id": report.get("content_id")},
                projection={"_id": 1, "u": 1, "isDeleted": 1}
            )
        elif report["type"] == "user":
            report["content"] = security.get_account(report.get("content_id"))

    # Return reports
    return {
        "error": False,
        "autoget": reports,
        "page#": query_args.page,
        "pages": get_total_pages("reports", {"reports.user": request.user}),
    }, 200


@me_bp.get("/export")
async def get_current_data_export():
    # Check authorization
    if not request.user:
        abort(401)

    # Get current data export request from the database
    data_export = db.data_exports.find_one({
        "user": request.user,
        "$or": [
            {"status": "pending"},
            {"completed_at": {"$gt": int(time.time())-604800}}
        ]
    }, projection={"error": 0})
    if not data_export:
        abort(404)

    # Return data export request
    return data_export, 200


@me_bp.post("/export")
async def request_data_export():
    # Check authorization
    if not request.user:
        abort(401)

    # Make sure a current data export request doesn't already exist
    if db.data_exports.count_documents({
        "user": request.user,
        "$or": [
            {"status": "pending"},
            {"completed_at": {"$gt": int(time.time())-604800}}
        ]
    }) > 0:
        abort(429)

    # Create data export request
    data_export = {
        "_id": str(uuid.uuid4()),
        "user": request.user,
        "status": "pending",
        "created_at": int(time.time())
    }
    db.data_exports.insert_one(data_export)

    # Tell the data export service to check for new requests
    rdb.publish("data_exports", "0")

    # Return data export request
    return data_export, 200

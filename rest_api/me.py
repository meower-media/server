from quart import Blueprint, current_app as app, request, abort
from quart_schema import validate_request, validate_querystring
from pydantic import BaseModel, Field
from typing import Optional, List
from copy import copy
import pymongo
import uuid
import time

import security
import models, errors
from entities import users
from database import db, rdb, get_total_pages
from uploads import claim_file, delete_file
from utils import log
from .utils import auto_ratelimit, check_auth


me_bp = Blueprint("me_bp", __name__, url_prefix="/me")


class DeleteAccountBody(BaseModel):
    password: str = Field(min_length=1, max_length=255)

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
    active_dms: Optional[List[str]] = Field(default=None)

    class Config:
        validate_assignment = True
        str_strip_whitespace = True

class ChangePasswordBody(BaseModel):
    old: str = Field(min_length=1, max_length=255)
    new: str = Field(min_length=8, max_length=72)

class GetReportsQueryArgs(BaseModel):
    page: Optional[int] = Field(default=1, ge=1)


@me_bp.get("/")
@check_auth()
async def get_me(requester: models.db.User):
    return users.db_to_v0(requester, include_private=True), 200


@me_bp.delete("/")
@validate_request(DeleteAccountBody)
@check_auth()
@auto_ratelimit("delete_acc", "user", 5, 300)
async def delete_account(data: DeleteAccountBody, requester: models.db.User):
    # Check password
    if not users.check_password_hash(data.password, requester["password"]):
        raise errors.InvalidCredentials
    
    # Schedule account for deletion
    users.delete_user(requester["_id"], delay=(60*60*24*7))

    # Disconnect clients
    for client in app.cl.usernames.get(request.user, []):
        client.kick(statuscode="LoggedOut")

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
    app.cl.broadcast({
        "mode": "update_config",
        "payload": new_config
    }, direct_wrap=True, usernames=[request.user])

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
        app.cl.broadcast({
            "mode": "update_profile",
            "payload": updated_profile_data
        }, direct_wrap=True)

    return {"error": False}, 200


@me_bp.get("/config/client")
async def get_client_settings():
    # Check authorization
    requester: models.db.User = request.user
    if not requester:
        abort(401)

    # Get and return settings
    return users.get_client_settings(requester["_id"], request.headers["Origin"])


@me_bp.patch("/config/client")
async def update_client_settings():
    # Check authorization
    requester: models.db.User = request.user
    if not requester:
        abort(401)

    # Get body
    try:
        body = await request.json
    except: abort(400)

    # Update settings
    users.update_client_settings(requester["_id"], request.headers["Origin"], body)
    
    return {"error": False}, 200


@me_bp.patch("/password")
@validate_request(ChangePasswordBody)
async def change_password(data: ChangePasswordBody):
    # Check authorization
    if not request.user:
        abort(401)

    # Check ratelimit
    if security.ratelimited(f"login:u:{request.user}:f"):
        abort(429)

    # Ratelimit
    security.ratelimit(f"login:u:{request.user}:f", 5, 60)

    # Check password
    account = db.usersv0.find_one({"_id": request.user}, projection={"pswd": 1})
    if not security.check_password_hash(data.old, account["pswd"]):
        return {"error": True, "type": "invalidCredentials"}, 401

    # Update password
    db.usersv0.update_one({"_id": request.user}, {"$set": {"pswd": security.hash_password(data.new)}})

    return {"error": False}, 200


@me_bp.delete("/tokens")
async def delete_tokens():
    # Check authorization
    if not request.user:
        abort(401)
    
    # Revoke tokens
    db.usersv0.update_one({"_id": request.user}, {"$set": {"tokens": []}})

    # Disconnect clients
    for client in app.cl.usernames.get(request.user, []):
        client.kick(statuscode="LoggedOut")

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
                {"_id": report.get("content_id")}, projection={"_id": 1, "u": 1, "isDeleted": 1}
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

    # Add download token that lasts 15 minutes
    if data_export["status"] == "completed":
        data_export["download_token"], _ = security.create_token("access_data_export", 900, {
            "id": data_export["_id"]
        })

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

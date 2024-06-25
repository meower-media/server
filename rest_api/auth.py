import re
from time import time
import uuid
from pydantic import BaseModel
from quart import Blueprint, request, abort, current_app as app
from quart_schema import validate_request
from pydantic import Field
from database import db, registration_blocked_ips
import security

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/admin")
time

class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=255)


@auth_bp.post('/login')
@validate_request(AuthRequest)
async def login(body: AuthRequest):
    for bucket_id in [
        f"login:i:{request.ip}",
        f"login:u:{body["username"]}:s",
        f"login:u:{body['username']}:f"
    ]:
        if security.ratelimited(bucket_id):
            abort(429)

    account = db.usersv0.find_one({"_id": body["username"]}, projection={
        "tokens": 1,
        "pswd": 1,
        "flags": 1,
        "permissions": 1,
        "ban": 1,
        "delete_after": 1
    })

    if not account:
        abort(404)

    if (account["flags"] & security.UserFlags.DELETED) or account["delete_after"] <= time.time() + 60:
        security.ratelimit(f"login:u:{body['username']}:f")
        return {"error": True, "type": "accountDeleted"}, 401

    if (body["password"] not in account["tokens"]) and (not security.check_password_hash(body["password"], account["pswd"])):
        security.ratelimit(f"login:u:{body['username']}:f")
        abort(401)

    db.netlog.update_one({"_id": {"ip": request.ip, "user": body["username"]}}, {"$set": {"last_used": int(time.time())}}, upsert=True)

    security.ratelimit(f"login:u:{body['username']}:s")

    token = security.generate_token()

    db.usersv0.update_one({"_id": body["username"]}, {
        "$addToSet": {"tokens": token},
        "$set": {"last_seen": int(time.time()), "delete_after": None}
    })

    return {"error": False, "token": token, "account":security.get_account(body["username"], True) }, 200

@auth_bp.post('/register')
@validate_request(AuthRequest)
async def register(body: AuthRequest):
    if not app.supporter.registration:
        return {"error": True, "type": "registrationDisabled"}, 403
    
    if security.ratelimited(f"register:{request.ip}:f"):
        abort(429)

    if not re.fullmatch(security.USERNAME_REGEX, body["username"]):
        return {"error": True, "type": "invalidUsername"}, 400
    
    if registration_blocked_ips.search_best(request.ip):
        security.ratelimit(f"register:{request.ip}:f")
        return {"error": True, "type": "registrationBlocked"}, 403

    if security.account_exists(body["username"]):
        security.ratelimit(f"register:{request.ip}:f")
        return {"error": True, "type": "usernameExists"}, 409

    token = security.generate_token()

    security.create_account(body["username"], body["password"], token)

    security.ratelimit(f"register:{request.ip}:s")

    db.netlog.update_one({"_id": {"ip": request.ip, "user": body["username"]}}, {"$set": {"last_used": int(time.time())}}, upsert=True)

    app.supporter.create_post("inbox", body["username"], "Welcome to Meower! We welcome you with open arms! You can get started by making friends in the global chat or home, or by searching for people and adding them to a group chat. We hope you have fun!")

    if security.get_netinfo(request.ip)["vpn"]:
        db.reports.insert_one({
            "_id": str(uuid.uuid4()),
            "type": "user",
            "content_id": body["username"],
            "status": "pending",
            "escalated": False,
            "reports": [{
                "user": "Server",
                "ip": request.ip,
                "reason": "User registered while using a VPN.",
                "comment": "",
                "time": int(time.time())
            }]
        })
    
    return {"error": False, "token": token, "account": security.get_account(body["username"], True)}, 200

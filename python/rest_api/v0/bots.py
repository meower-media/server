import os
import uuid
from typing import TYPE_CHECKING

import requests
from quart import Blueprint, current_app as app, request, abort
from quart_schema import validate_request
from pydantic import BaseModel

import security
import secrets

from database import db

if TYPE_CHECKING:
	class Reqest:
		user: str
		flags: int
		permissions: int

	request: Reqest

	from cloudlink import CloudlinkServer
	from supporter import Supporter
	class App:
		supporter: "Supporter"
		cl: "CloudlinkServer"


	app: App

bots_bp = Blueprint("bots", __name__, url_prefix="/bots")

class CreateBot(BaseModel):
	name: str
	description: str
	captcha: str

class SecureRequests(BaseModel):
	mfa_code: int

@bots_bp.post("/")
@validate_request(CreateBot)
async def create_bot(data: CreateBot):
	if not request.user:
		abort(401)

	if os.getenv("CAPTCHA_SECRET") and not (hasattr(request, "bypass_captcha") and request.bypass_captcha):
		if not requests.post("https://api.hcaptcha.com/siteverify", data={
			"secret": os.getenv("CAPTCHA_SECRET"),
			"response": data.captcha,
		}).json()["success"]:
			return {"error": True, "type": "invalidCaptcha"}, 403

	if not (security.ratelimited(f"bot:create:{request.user}")):
		abort(429)


	if any([
		db.users.find_one({"lower_username": data.name.lower()}),
		db.bots.find_one({"name": data.name})
	]):
		return {"error": True, "type": "nameTaken"}, 409

	token = secrets.token_urlsafe(32)

	bot = {
		"_id": str(uuid.uuid4()),
		"token": security.hash_password(token),
		"name": data.name,
		"description": data.description,
		"owner": request.user,
		"avatar": {
			"default": 1,
			"custom": None
		}
	}

	db.bots.insert_one(bot)
	security.ratelimit(f"bot:create:{request.user}", 1, 60)

	bot["token"] = token
	bot["error"] = False

	return bot, 200


@bots_bp.get("/")
async def get_bots():
	if not request.user:
		abort(401)

	bots = list(db.bots.find({"owner": request.user}, projection={"_id": 1, "name": 1, "avatar": 1}))
	return {"error": False, "bots": bots}, 200

@bots_bp.get("/<bot_id>")
async def get_bot(bot_id: str):
	if not request.user:
		abort(401)

	bot = db.bots.find_one({"_id": bot_id, "owner": request.user}, projection={"token": 0})
	if not bot:
		abort(404)

	return {"error": False, "bot": bot}, 200

@bots_bp.delete("/<bot_id>")
@validate_request(SecureRequests)
async def delete_bot(bot_id: str, data: SecureRequests):
	if not request.user:
		abort(401)

	bot = db.bots.find_one({"_id": bot_id, "owner": request.user})
	if not bot:
		abort(404)

	if not security.check_mfa(request.user, data.mfa_code):
		return {"error": True, "type": "invalidMfa"}, 403

	db.bots.delete_one({"_id": bot_id})
	return {"error": False}, 200
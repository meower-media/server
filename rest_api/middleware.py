from flask import Blueprint, request, abort
from flask import current_app as app
import os

router = Blueprint("middleware", __name__)

@router.before_request
async def ip_middleware():
    if (os.getenv("TRUST_PROXY", "false") == "true") and ("x-forwarded-for" in request.headers):
        request.remote_addr = request.headers["x-forwarded-for"]

    if request.remote_addr in app.server.ip_blocklist:
        abort(403)

@router.before_request
async def repair_mode_middleware():
    if app.server.reject_clients:
        abort(503)

@router.before_request
async def auth_middleware():
    request.user = None

    if ("username" in request.headers) and ("token" in request.headers):
        username = request.headers["username"]
        token = request.headers["token"]

        result = app.accounts.authenticate_token(username, token)
        if result != app.accounts.accountAuthenticated:
            abort(401)
        
        request.user = app.accounts.get_account(username)
        if not isinstance(request.user, dict):
            abort(401)

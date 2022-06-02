from flask import Blueprint, request, abort
from flask import current_app as app

users = Blueprint("users_blueprint", __name__)

@users.route("/<user>", methods=["GET"])
def get_profile(user):
    if not request.authed:
        abort(401)

    # Get user data
    file_read, userdata = app.meower.accounts.get_account(user)
    if not file_read:
        abort(404)

    return app.respond(userdata["profile"], 200, error=False)
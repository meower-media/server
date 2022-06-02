from flask import Blueprint, request, abort
from flask import current_app as app

search = Blueprint("search_blueprint", __name__)

@search.route("/profiles", methods=["GET"])
def search_profiles():
    if not request.authed:
        abort(401)

    if "q" in request.args:
        query = request.args["q"]

    # Get user data
    file_read, userdata = app.meower.accounts.get_account(user)
    if not file_read:
        abort(404)

    return app.respond(userdata["profile"], 200, error=False)
from flask import Blueprint, request, abort
from flask import current_app as app

home = Blueprint("home_blueprint", __name__)

@home.route("/", methods=["GET", "POST"])
def get_home():
    if request.method == "GET":
        # Get index
        query_get = app.meower.files.find_items("posts", {"post_origin": "home", "isDeleted": False}, sort="t.e", truncate=True)

        # Auto get
        if not ("autoget" in request.args):
            del query_get["items"]

        # Return payload
        return app.respond(query_get, 200)
    elif request.method == "POST":
        if not ("content" in request.form):
            return app.respond({"type": "missingField"}, 400, error=True)
    
        # Extract content for simplicity
        content = request.form.get("content")

        # Check for bad datatypes and syntax
        if not (type(content) == str):
            return app.respond({"type": "badDatatype"}, 400, error=True)
        elif len(content) > 360:
            return app.respond({"type": "fieldTooLarge"}, 400, error=True)
        elif app.meower.supporter.checkForBadCharsPost(content):
            return app.respond({"type": "illegalCharacters"}, 400, error=True)
        elif app.meower.supporter.check_for_spam(request.session.user):
            return app.respond({"type": "ratelimited"}, 429, error=True)

        file_read, userdata = app.meower.accounts.get_account(request.session.user)
        if not file_read:
            abort(500)
        elif userdata["flags"]["suspended"]:
            return app.respond({"type": "accountSuspended"}, 403, error=True)

        # Create post
        file_write, postdata = app.meower.posts.create_post("home", request.session.user, content)
        if not file_write:
            abort(500)
        else:
            # Ratelimit client
            app.meower.supporter.ratelimit(request.session.user)

        # Return payload
        return app.respond(postdata, 200, error=False)
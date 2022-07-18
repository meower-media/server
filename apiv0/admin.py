from flask import Blueprint, request, render_template
from flask import current_app as app

admin = Blueprint("admin_blueprint", __name__)

@admin.route("/login", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("login.html"), 200
    elif request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        file_read, userdata = app.meower.accounts.get_account(username)
        if not file_read:
            return render_template("login.html", error="Account not found."), 401
        elif not (userdata["userdata"]["lvl"] > 0):
            return render_template("login.html", error="Account is not a moderator."), 401
        elif (app.meower.accounts.check_password(username, password) != (True, True)):
            return render_template("login.html", error="Password is incorrect."), 401
        else:
            return "You made it!", 200

@admin.route("/users", methods=["GET"])
def users():
    if "search" in request.args:
        all_users = []
        index = app.meower.files.find_items("usersv0", {"lower_username": {"$regex": request.args["search"]}}, sort="lower_username", autoget=True)
        for user in index["items"]:
            all_users.append({"username": user["_id"], "mfa": (user["mfa_secret"] is not None), "admin": (user["lvl"] > 0), "deleted": user["flags"]["isDeleted"], "created": user["created_at"], "last_login": user["last_login"]})
        return render_template("users.html", search_results=all_users, search_results_count=len(all_users)), 200

    return render_template("users.html"), 200
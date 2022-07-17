from flask import Blueprint, request, send_file
from flask import current_app as meower
import os
import time
from jinja2 import Template
from threading import Thread

general = Blueprint("general_blueprint", __name__)

@general.route("/", methods=["GET"])
def index():
    return meower.respond("Welcome to the Meower API!", 200)

@general.route("/status", methods=["GET"])
def get_status():
    data = meower.db["config"].find_one({"_id": "supported_versions"})
    return meower.respond({"isRepairMode": meower.repairMode, "scratchDeprecated": meower.scratchDeprecated, "supported": {"0": (0 in data["apis"])}, "supported_clients": data["clients"], "IPBlocked": (request.remote_addr in meower.ip_banlist)}, 200)

@general.route("/email", methods=["GET"])
def email_action():
    # Check for required data
    meower.check_for_params(["token"])

    # Extract token for simplicity
    token = request.args["token"]

    # Get session
    session = meower.db["sessions"].find_one({"token": token, "type": 0, "expires": {"$gt": time.time()}})

    # Check if session exists
    if session is None:
        return meower.respond({"type": "unauthorized", "message": "You are not authenticated."}, 401, error=True)

    # Get session action
    if session["action"] == "verify":
        # Get user
        userdata = meower.db["usersv0"].find_one({"_id": session["user"]})

        # Check if user exists
        if userdata is None:
            return meower.respond({"type": "unauthorized", "message": "You are not authenticated."}, 401, error=True)

        # Set email
        meower.db["usersv0"].update_one({"_id": session["user"]}, {"$set": {"security.email": session["email"]}})

        # Make user verified
        if userdata["state"] == 0:
            meower.db["usersv0"].update_one({"_id": session["user"]}, {"$set": {"state": 1}})

        # Delete session
        meower.db["sessions"].delete_one({"_id": session["_id"]})

        # Return payload
        return meower.respond({}, 200, error=False)
    elif session["action"] == "download-data":
        # Check if data package exists
        if not ("{0}.zip".format(session["user"]) in os.listdir("apiv0/data_exports")):
            meower.db["sessions"].delete_one({"_id": session["_id"]})
            return meower.respond({"type": "unauthorized", "message": "You are not authenticated."}, 401, error=True)

        # Return data package
        return send_file("apiv0/data_exports/{0}.zip".format(session["user"]), as_attachment=True)
    elif session["action"] == "delete-account":
        # Delete sessions
        meower.db["sessions"].delete_many({"user": session["user"]})

        # Schedule user for deletion
        meower.db["usersv0"].update_one({"_id": session["user"]}, {"$set": {"security.delete_after": time.time()+172800}})

        # Send alert to user
        userdata = meower.db["usersv0"].find_one({"_id": session["user"]})
        email = meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
        with open("apiv0/email_templates/alerts/account_deletion.html", "r") as f:
            email_template = Template(f.read()).render({"username": userdata["username"]})
        Thread(target=meower.send_email, args=(email, userdata["username"], "Account scheduled for deletion", email_template,), kwargs={"type": "text/html"}).start()

        # Return payload
        return meower.respond({}, 200, error=False)
    else:
        # Invalid action
        meower.db["sessions"].delete_one({"_id": session["_id"]})
        return meower.respond({"type": "unauthorized", "message": "You are not authenticated."}, 401, error=True)

@general.route('/favicon.ico', methods=['GET']) # Favicon, my ass. We need no favicon for an API.
def favicon_my_ass():
    return meower.respond("", 204, error=False)
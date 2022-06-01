from flask import Blueprint, request
from flask import current_app as app

general = Blueprint("general_blueprint", __name__)

@general.route("/", methods=["GET"])
def index():
    return app.respond("Welcome to the Meower API!", 200)

@general.route("/status", methods=["GET"])
def get_status():
    file_read, data = app.meower.files.load_item("config", "supported_versions")
    return app.respond({"isRepairMode": app.meower.supporter.repair_mode, "scratchDeprecated": app.meower.supporter.is_deprecated, "supported": {"0": True}, "supported_clients": data["index"]}, 200)
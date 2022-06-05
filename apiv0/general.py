from flask import Blueprint, request
from flask import current_app as meower

general = Blueprint("general_blueprint", __name__)

@general.route("/", methods=["GET"])
def index():
    return meower.respond("Welcome to the Meower API!", 200)

@general.route("/status", methods=["GET"])
def get_status():
    file_read, data = meower.files.load_item("config", "supported_versions")
    return meower.respond({"isRepairMode": meower.supporter.repair_mode, "scratchDeprecated": meower.supporter.is_deprecated, "supported": {"0": True}, "supported_clients": data["index"]}, 200)
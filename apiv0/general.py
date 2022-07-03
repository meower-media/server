from flask import Blueprint, request
from flask import current_app as meower

general = Blueprint("general_blueprint", __name__)

@general.route("/", methods=["GET"])
def index():
    return meower.respond("Welcome to the Meower API!", 200)

@general.route("/status", methods=["GET"])
def get_status():
    data = meower.db["config"].find_one({"_id": "supported_versions"})
    return meower.respond({"isRepairMode": meower.repairMode, "scratchDeprecated": meower.scratchDeprecated, "supported": {"0": (0 in data["apis"])}, "supported_clients": data["clients"], "IPBlocked": (request.remote_addr in meower.ip_banlist)}, 200)
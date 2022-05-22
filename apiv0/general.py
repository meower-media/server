from flask import Blueprint, request
from flask import current_app as app

general = Blueprint("general_blueprint", __name__)

@general.route("/", methods=["GET"])
def index():
    return app.respond({"supported_versions": ["v0"], "version_endpoints": {"v0": "/v0"}}, 200)

@general.route("/status", methods=["GET"])
def get_status():
    return app.respond({"isRepairMode": app.meower.supporter.repair_mode, "scratchDeprecated": app.meower.supporter.is_deprecated}, 200)

@general.route("/ip", methods=["GET"])
def ip_fetcher():
    if "Cf-Connecting-Ip" in request.headers:
        return app.respond(str(request.headers["Cf-Connecting-Ip"]), 200)
    else:
        return app.respond(str(request.remote_addr), 200)
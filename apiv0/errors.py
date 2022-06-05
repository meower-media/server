from flask import Blueprint, request
from flask import current_app as app

errors = Blueprint("errors_blueprint", __name__)

@errors.app_errorhandler(400)
def bad_request(e):
    return app.respond({"type": "badRequest"}, 400, error=True)

@errors.app_errorhandler(401)
def not_authenticated(e):
    return app.respond({"type": "notAuthenticated"}, 401, error=True)

@errors.app_errorhandler(403)
def forbidden(e):
    return app.respond({"type": "missingPermissions"}, 403, error=True)

@errors.app_errorhandler(404)
def not_found(e):
    return app.respond({"type": "notFound"}, 404, error=True)

@errors.app_errorhandler(405)
def method_not_allowed(e):
    return app.respond({"type": "methodNotAllowed"}, 405, error=True)

@errors.app_errorhandler(500)
def internal(e):
    return app.respond({"type": "internal"}, 500, error=True)
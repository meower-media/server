from flask import Blueprint, request
from flask import current_app as app

errors = Blueprint("errors_blueprint", __name__)

@errors.app_errorhandler(400)
def bad_request(e):
    return app.respond({"type": "badRequest", "message": "Bad request"}, 400, error=True)

@errors.app_errorhandler(401)
def not_authenticated(e):
    return app.respond({"type": "notAuthenticated", "message": "Not authenticated"}, 401, error=True)

@errors.app_errorhandler(403)
def forbidden(e):
    return app.respond({"type": "forbidden", "message": "You do not have permission to use this resource"}, 403, error=True)

@errors.app_errorhandler(404)
def not_found(e):
    return app.respond({"type": "notFound", "message": "The requested resource was not found"}, 404, error=True)

@errors.app_errorhandler(405)
def method_not_allowed(e):
    return app.respond({"type": "methodNotAllowed", "message": "Endpoint does not support this method"}, 405, error=True)

@errors.app_errorhandler(429)
def too_many_requests(e):
    return app.respond({"type": "ratelimited", "message": "You are being ratelimited"}, 429, error=True)

@errors.app_errorhandler(500)
def internal(e):
    return app.respond({"type": "internal", "message": "An unexpected internal server error occurred"}, 500, error=True)
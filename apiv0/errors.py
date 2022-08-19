from flask import Blueprint, request
from flask import current_app as meower

errors = Blueprint("errors_blueprint", __name__)

@errors.app_errorhandler(400)
def bad_request(e):
    return meower.resp(400)

@errors.app_errorhandler(401)
def not_authenticated(e):
    return meower.resp(401)

@errors.app_errorhandler(403)
def forbidden(e):
    return meower.resp(403)

@errors.app_errorhandler(404)
def not_found(e):
    return meower.resp(404)

@errors.app_errorhandler(405)
def method_not_allowed(e):
    return meower.resp(405)

@errors.app_errorhandler(429)
def too_many_requests(e):
    return meower.resp(429)

@errors.app_errorhandler(500)
def internal(e):
    return meower.resp(500)
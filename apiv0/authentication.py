from flask import Blueprint, request
from flask import current_app as app

auth = Blueprint("authentication_blueprint", __name__)
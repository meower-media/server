import flask
from flask import Flask, Response, request
from flask_cors import CORS

from apiv0.respond import respond
from apiv0.errors import errors
from apiv0.general import general
from apiv0.admin import admin
from apiv0.authentication import auth
from apiv0.users import users
from apiv0.home import home
from apiv0.chats import chats
from apiv0.search import search

class REST_API:
    def __init__(self, meower, ip="0.0.0.0", port=3001):
        # Initialize API
        self.meower = meower
        self.app = Flask(__name__)
        self.app.respond = respond
        self.app.meower = meower

        # Register blueprints
        self.app.register_blueprint(errors)
        self.app.register_blueprint(general, name="compatibility_general") # Keep general endpoints as root for compatibility
        self.app.register_blueprint(general, url_prefix="/v0")
        self.app.register_blueprint(admin, url_prefix="/admin")
        self.app.register_blueprint(auth, url_prefix="/v0/me")
        self.app.register_blueprint(users, url_prefix="/v0/users")
        self.app.register_blueprint(home, url_prefix="/v0/home")
        self.app.register_blueprint(chats, url_prefix="/v0/chats")
        self.app.register_blueprint(search, url_prefix="/v0/search")

        CORS(self.app, resources={r'*': {'origins': '*'}})

        # Run Flask app
        self.app.run(host=ip, port=port)
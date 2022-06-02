import flask
from flask import Flask, Response, request
from flask_cors import CORS

from apiv0.respond import respond
from apiv0.errors import errors
from apiv0.general import general
from apiv0.authentication import auth
from apiv0.users import users
from apiv0.posts import posts
from apiv0.chats import chats

class REST_API:
    def __init__(self, meower, ip="0.0.0.0", port=3001):
        # Initialize API
        self.meower = meower
        self.app = Flask(__name__)
        self.app.respond = respond
        self.app.meower = meower

        # Register blueprints
        self.app.register_blueprint(errors)
        #self.app.register_blueprint(general, name="compatibility_general") # Keep general endpoints as root for compatibility
        self.app.register_blueprint(general, url_prefix="/v0")
        self.app.register_blueprint(auth, url_prefix="/v0/me")
        self.app.register_blueprint(users, url_prefix="/v0/users")
        self.app.register_blueprint(posts, url_prefix="/v0/posts")
        self.app.register_blueprint(chats, url_prefix="/v0/chats")

        CORS(self.app, resources={r'*': {'origins': '*'}})

        # Run Flask app
        self.app.run(host=ip, port=port)
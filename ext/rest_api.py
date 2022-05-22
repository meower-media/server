import flask
from flask import Flask, Response, request
from flask_cors import CORS

from apiv0.respond import respond
from apiv0.errors import errors
from apiv0.general import general
from apiv0.posts import posts

class REST_API:
    def __init__(self, meower, ip="0.0.0.0", port=3001):
        # Initialize API
        self.meower = meower
        self.app = Flask(__name__)
        self.cors = CORS(self.app, resources=r'*')
        self.app.respond = respond
        self.app.meower = meower

        # Register blueprints
        self.app.register_blueprint(errors)
        self.app.register_blueprint(general, url_prefix="/v0")
        self.app.register_blueprint(posts, url_prefix="/v0/posts")

        # Run Flask app
        self.app.run(host=ip, port=port)
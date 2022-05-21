import flask
from flask import Flask, Response, request
from flask_cors import CORS
from apiv1.endpoints import Endpoints

from apiv1.respond import respond
from apiv1.errors import Errors
from apiv1.endpoints import Endpoints

class REST_API:
    def __init__(self, meower, ip="0.0.0.0", port=3000):
        self.app = Flask(__name__)
        self.cors = CORS(self.app, resources=r'*')

        self.app.meower = meower

        self.app.respond = respond

        self.app.errors = Errors(self.app)
        for item in self.app.errors.all_errors:
            self.app.register_error_handler(item["error_status"], item["error_function"])

        self.app.endpoints = Endpoints(self.app)
        for item in self.app.endpoints.all_endpoints:
            self.app.add_url_rule("/v1"+item["endpoint_path"], item["endpoint_name"], item["endpoint_function"], methods=["GET"])

        self.app.run(host=ip, port=port)
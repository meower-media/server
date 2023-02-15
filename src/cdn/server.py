from sanic import Sanic, Blueprint
import os

# General imports
from .errors import MeowerErrorHandler
from .middleware import ratelimit_header

# Initialize CDN server
app = Sanic("MeowerCDN")
app.config.REAL_IP_HEADER = os.getenv("IP_HEADER")
app.config.REQUEST_MAX_SIZE = 20000000
app.error_handler = MeowerErrorHandler()
app.register_middleware(ratelimit_header, "response")
app.static("/assets", "./assets")

# Initialize v1 CDN Blueprints
from .uploads import v1 as v1_uploads
app.blueprint(Blueprint.group(
    v1_uploads,
    version=1
))

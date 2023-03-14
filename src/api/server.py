from sanic import Sanic, Blueprint, HTTPResponse
import time
import os

from .errors import MeowerErrorHandler
from .middleware import parse_ua, cors_headers, ratelimit_headers
from src.util import status


# Initialize API server
app = Sanic("MeowerAPI")
app.config.REAL_IP_HEADER = os.getenv("IP_HEADER")
app.config.REQUEST_MAX_SIZE = 10000000
app.error_handler = MeowerErrorHandler()
app.register_middleware(parse_ua, "request")
app.register_middleware(cors_headers, "response")
app.register_middleware(ratelimit_headers, "response")


# Initialize unversioned API Blueprints
from .general import unversioned as unversioned_general
unversioned_bp = Blueprint.group(
    unversioned_general
)
app.blueprint(unversioned_bp)


# Initialize v0 API Blueprints 
from .general import v0 as v0_general
from .me import v0 as v0_me
from .home import v0 as v0_home
from .posts import v0 as v0_posts
from .users import v0 as v0_users
from .search import v0 as v0_search
v0_bp = Blueprint.group(
    v0_general,
    v0_me,
    v0_home,
    v0_posts,
    v0_users,
    v0_search
)
@v0_bp.middleware("request")
async def v0_middleware(request):
    # Check whether v0 has been discontinued
    if time.time() > 1688169599:
        raise status.endpointNotFound
app.blueprint(v0_bp)


# Initialize v1 API Blueprints
from .general import v1 as v1_general
from .authentication import v1 as v1_authentication
from .email import v1 as v1_email
from .me import v1 as v1_me
from .home import v1 as v1_home
from .posts import v1 as v1_posts
from .users import v1 as v1_users
from .chats import v1 as v1_chats
from .invites import v1 as v1_invites
from .applications import v1 as v1_applications
from .search import v1 as v1_search
v1_bp = Blueprint.group(
    v1_general,
    v1_authentication,
    v1_email,
    v1_me,
    v1_home,
    v1_posts,
    v1_users,
    v1_chats,
    v1_invites,
    v1_applications,
    v1_search,
    version=1
)
app.blueprint(v1_bp)

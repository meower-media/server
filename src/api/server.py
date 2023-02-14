from sanic import Sanic, Blueprint
import time
import os

# General imports
from .errors import MeowerErrorHandler
from .middleware import parse_ua, ratelimit_header

# Initialize API server
app = Sanic("MeowerAPI")
app.config.REAL_IP_HEADER = os.getenv("IP_HEADER")
app.config.REQUEST_MAX_SIZE = 10000000
app.error_handler = MeowerErrorHandler()
app.register_middleware(parse_ua, "request")
app.register_middleware(ratelimit_header, "response")

# Start v0 API
if not time.time() > 1688169599:  # Check whether v0 has been discontinued
    from .general import v0 as v0_general
    from .home import v0 as v0_home
    from .posts import v0 as v0_posts
    from .users import v0 as v0_users
    from .search import v0 as v0_search
    app.blueprint(Blueprint.group(
        v0_general,
        v0_home,
        v0_posts,
        v0_users,
        v0_search
    ))

# Start v1 API
from .general import v1 as v1_general
from .authentication import v1 as v1_authentication
from .me import v1 as v1_me
from .home import v1 as v1_home
from .posts import v1 as v1_posts
from .users import v1 as v1_users
from .chats import v1 as v1_chats
from .uploads import v1 as v1_uploads
from .applications import v1 as v1_applications
from .search import v1 as v1_search
app.blueprint(Blueprint.group(
    v1_general,
    v1_authentication,
    v1_me,
    v1_home,
    v1_posts,
    v1_users,
    v1_chats,
    v1_uploads,
    v1_applications,
    v1_search,
    version=1
))

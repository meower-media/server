from sanic import Sanic, Blueprint
from dotenv import load_dotenv
import time
import os

# Load env variables
load_dotenv()

# General imports
from .errors import MeowerErrorHandler
from .middleware import parse_ua

# Initialize API server
app = Sanic("MeowerAPI")
app.config.REAL_IP_HEADER = os.getenv("IP_HEADER")
app.error_handler = MeowerErrorHandler()
app.register_middleware(parse_ua, "request")

# Start v0 API
if time.time() < 1674532540:  # Check whether v0 has been discontinued
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
from .search import v1 as v1_search
app.blueprint(Blueprint.group(
    v1_general,
    v1_authentication,
    v1_me,
    v1_home,
    v1_posts,
    v1_users,
    v1_chats,
    v1_search,
    version=1
))
from sanic import Sanic, Blueprint
from sanic_limiter import Limiter, get_remote_address
from dotenv import load_dotenv
import os

load_dotenv()

from .errors import MeowerErrorHandler
from .middleware import parse_ua, authorization, get_ratelimit_id
from .me import v1 as v1_me
from .home import v1 as v1_home
from .posts import v1 as v1_posts

v1 = Blueprint.group(
    v1_me,
    v1_home,
    v1_posts,
    version=1
)

app = Sanic("MeowerAPI")
limiter = Limiter(app, global_limits=["1/minute"], key_func=get_ratelimit_id)
app.config.REAL_IP_HEADER = os.getenv("IP_HEADER")
app.error_handler = MeowerErrorHandler()
app.register_middleware(parse_ua, "request")
app.register_middleware(authorization, "request")
app.blueprint(v1)

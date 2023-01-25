from sanic import Blueprint

# v1
from .account import v1 as v1_account
from .profile import v1 as v1_profile
v1 = Blueprint.group(
    v1_account,
    v1_profile,
    url_prefix="/me"
)

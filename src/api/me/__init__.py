from sanic import Blueprint

# v1
from .register import v1 as v1_register
from .login import v1 as v1_login
v1 = Blueprint.group(
    v1_register,
    v1_login,
    url_prefix="/me"
)

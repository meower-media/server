from sanic import Blueprint

# v1
from .account import v1 as v1_account
from .profile import v1 as v1_profile
from .sessions import v1 as v1_sessions
#from .sync import v1 as v1_sync
from .inbox import v1 as v1_inbox
v1 = Blueprint.group(
    v1_account,
    v1_profile,
    v1_sessions,
    #v1_sync,
    v1_inbox,
    url_prefix="/me"
)

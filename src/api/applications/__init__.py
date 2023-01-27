from sanic import Blueprint

from src.util import status
from src.entities import users, applications

def get_application_or_abort_if_not_maintainer(application_id: str, user: users.User):
    application = applications.get_application(application_id)
    if (application is None) or (not application.has_maintainer(user)):
        raise status.notFound
    return application

def get_application_or_abort_if_not_owner(application_id: str, user: users.User):
    application = applications.get_application(application_id)
    if (application is None) or (application.owner_id != user.id):
        raise status.notFound
    return application

# v1
from .general import v1 as v1_general
from .oauth2 import v1 as v1_oauth2
from .bot import v1 as v1_bot
v1 = Blueprint.group(
    v1_general,
    v1_oauth2,
    v1_bot,
    url_prefix="/applications"
)

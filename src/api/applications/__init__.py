from sanic import Blueprint

from src.util import status
from src.entities import users, applications


def get_application_or_abort_if_not_maintainer(application_id: str, user: any):
    application = applications.get_application(application_id)
    if application and application.has_maintainer(user):
        return application
    else:
        raise status.resourceNotFound


def get_application_or_abort_if_not_owner(application_id: str, user: any):
    application = applications.get_application(application_id)
    if application and (application.owner_id == user.id):
        return application
    else:
        raise status.resourceNotFound


# v1
from .general import v1 as v1_general
from .oauth2 import v1 as v1_oauth2
from .bot import v1 as v1_bot
from .migrate import v1 as v1_migrate

v1 = Blueprint.group(
    v1_general,
    v1_oauth2,
    v1_bot,
    v1_migrate,
    url_prefix="/applications"
)

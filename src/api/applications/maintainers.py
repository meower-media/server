from sanic import Blueprint, HTTPResponse, json

from . import get_application_or_abort_if_not_maintainer, get_application_or_abort_if_not_owner
from src.util import status, security
from src.entities import users

v1 = Blueprint("v1_applications_maintainers", url_prefix="/<application_id:str>/maintainers/<maintainer_id:str>")


@v1.put("/")
@security.sanic_protected(allow_bots=False)
async def v1_add_application_maintainer(request, application_id: str, maintainer_id: str):
    # Get application
    application = get_application_or_abort_if_not_owner(application_id, request.ctx.user)

    # Add maintainer
    application.add_maintainer(users.get_user(maintainer_id))

    return json(application.client)


@v1.delete("/")
@security.sanic_protected(allow_bots=False)
async def v1_remove_application_maintainer(request, application_id: str, maintainer_id: str):
    # Get application
    application = get_application_or_abort_if_not_maintainer(application_id, request.ctx.user)

    # Remove maintainer
    if (request.ctx.user.id != maintainer_id) and (request.ctx.user.id != application.owner_id):
        raise status.missingPermissions
    application.remove_maintainer(users.get_user(maintainer_id))

    if request.ctx.user.id == maintainer_id:
        return HTTPResponse(status=204)
    else:
        return json(application.client)


@v1.post("/transfer")
@security.sanic_protected(allow_bots=False)
async def v1_transfer_application_ownership(request, application_id: str, maintainer_id: str):
    # Get application
    application = get_application_or_abort_if_not_owner(application_id, request.ctx.user)

    # Transfer ownership
    application.transfer_ownership(users.get_user(maintainer_id))

    return json(application.client)

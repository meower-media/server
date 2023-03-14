from sanic import Blueprint, HTTPResponse, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from . import get_application_or_abort_if_not_maintainer, get_application_or_abort_if_not_owner
from src.util import status, security
from src.entities import applications

v1 = Blueprint("v1_applications_general", url_prefix="/")


class CreateApplicationForm(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=20
    )


class EditApplicationForm(BaseModel):
    name: Optional[str] = Field(
        min_length=1,
        max_length=20
    )
    description: Optional[str] = Field(
        max_length=500
    )


@v1.get("/")
@security.v1_protected(allow_bots=False)
async def v1_get_applications(request):
    fetched_applications = applications.get_user_applications(request.ctx.user)
    return json([application.client for application in fetched_applications])


@v1.post("/")
@validate(json=CreateApplicationForm)
@security.v1_protected(allow_bots=False, ignore_suspension=False)
async def v1_create_applications(request, body: CreateApplicationForm):
    application = applications.create_application(body.name, request.ctx.user)
    return json(application.client)


@v1.get("/<application_id:str>")
@security.v1_protected(allow_bots=False)
async def v1_get_application(request, application_id: str):
    application = get_application_or_abort_if_not_maintainer(application_id, request.ctx.user)
    return json(application.client)


@v1.patch("/<application_id:str>")
@validate(json=EditApplicationForm)
@security.v1_protected(allow_bots=False, ignore_suspension=False)
async def v1_update_application(request, application_id: str, body: EditApplicationForm):
    # Get application
    application = get_application_or_abort_if_not_maintainer(application_id, request.ctx.user)

    # Edit application
    application.edit(name=body.name, description=body.description)

    return json(application.client)


@v1.delete("/<application_id:str>")
@security.v1_protected(allow_bots=False)
async def v1_delete_application(request, application_id: str):
    # Get application
    application = get_application_or_abort_if_not_owner(application_id, request.ctx.user)

    # Delete application
    application.delete()

    return HTTPResponse(status=204)

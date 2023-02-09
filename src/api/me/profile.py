from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional, Union

from src.util import security

v1 = Blueprint("v1_me_profile", url_prefix="/profile")


class UpdateProfileForm(BaseModel):
    username: Optional[str] = Field(
        min_length=1,
        max_length=20
    )
    quote: str = Field(
        max_length=500
    )
    icon_type: int = Field(
        ge=0,
        le=2
    )
    icon_data: Union[int, str] = Field(
        max_length=255
    )


class UpdateProfileThemeForm(BaseModel):
    main: Optional[str] = Field(
        max_length=10
    )
    main_alternate: Optional[str] = Field(
        max_length=10
    )
    main_highlight: Optional[str] = Field(
        max_length=10
    )
    main_shadow: Optional[str] = Field(
        max_length=10
    )
    background: Optional[str] = Field(
        max_length=10
    )
    text: Optional[str] = Field(
        max_length=10
    )
    text_on_main: Optional[str] = Field(
        max_length=10
    )


@v1.get("/")
@security.sanic_protected()
async def v1_get_profile(request):
    return json(request.ctx.user.client)


@v1.patch("/")
@validate(json=UpdateProfileForm)
@security.sanic_protected(allow_bots=False, ignore_suspension=False)
async def v1_update_profile(request, body: UpdateProfileForm):
    if body.username:
        request.ctx.user.update_username(body.username)
    if body.quote:
        request.ctx.user.update_quote(body.quote)

    return json(request.ctx.user.client)


@v1.patch("/theme")
@validate(json=UpdateProfileThemeForm)
@security.sanic_protected(allow_bots=False, ignore_suspension=False)
async def v1_update_profile_theme(request, body: UpdateProfileThemeForm):
    request.ctx.user.update_theme(request.json)

    return json(request.ctx.user.client)

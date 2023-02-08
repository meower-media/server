from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from src.util import security

v1 = Blueprint("v1_me_sync", url_prefix="/sync")

class UpdateConfig(BaseModel):
    theme: Optional[str] = Field(
        max_length=2000
    )
    notifications: Optional[int] = Field(
        ge=0,
        le=63
    )
    direct_messages: Optional[int] = Field(
        ge=0,
        le=2
    )
    filter: Optional[bool] = Field()
    debug: Optional[bool] = Field()

@v1.get("/config")
@security.sanic_protected(allow_bots=False, ignore_ban=True)
async def v1_get_config(request):
    return json(request.ctx.user.config)

@v1.patch("/config")
@validate(json=UpdateConfig)
@security.sanic_protected(allow_bots=False, ignore_ban=True)
async def v1_update_config(request, body: UpdateConfig):
    request.ctx.user.update_config(request.json)
    
    return json(request.ctx.user.config)

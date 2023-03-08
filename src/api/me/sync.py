from sanic import Blueprint, json

from src.util import security


v1 = Blueprint("v1_me_sync", url_prefix="/sync")


@v1.get("/config")
@security.v1_protected(allow_bots=False, ignore_ban=True)
async def v1_get_user_config(request):
    return json(request.ctx.user.config)


@v1.patch("/config")
@security.v1_protected(allow_bots=False, ignore_ban=True)
async def v1_update_user_config(request):
    new_config = request.ctx.user.update_config(request.json)

    return json(new_config)

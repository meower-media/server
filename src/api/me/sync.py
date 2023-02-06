from sanic import Blueprint, json
from sys import getsizeof
from json import dumps as json_encode

from src.util import status, security

v1 = Blueprint("v1_me_sync", url_prefix="/sync")

@v1.get("/")
@security.sanic_protected(allow_bots=False, ignore_ban=True)
async def v1_get_sync(request):
    return json(request.ctx.user.sync)

@v1.patch("/")
@security.sanic_protected(allow_bots=False, ignore_suspension=False)
async def v1_update_sync(request):
    if getsizeof(json_encode(request.json)) > 1024:
        raise status.missingPermissions  # placeholder

    request.ctx.user.update_sync(request.json)
    
    return json(request.ctx.user.sync)

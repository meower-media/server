from sanic import Blueprint, json
from sanic.response import raw

from src.util import status, security
from src.entities import uploads

v1 = Blueprint("v1_uploads", url_prefix="/uploads")

@v1.get("/<hash:str>/<token:str>")
async def v1_get_upload(request, hash: str, token: str):
    # Get upload
    upload = uploads.get_upload(hash)

    # Check token
    if token not in upload.tokens:
        raise status.notFound  # placeholder

    return raw(upload.data)

@v1.post("/")
@security.sanic_protected(allow_bots=False, ignore_suspension=False)
async def v1_create_upload(request):
    # Get file
    file = request.files.get("file")
    if not file:
        raise status.missingPermissions  # placeholder
    
    # Store file
    upload = uploads.create_upload(request.ctx.user, file.name, file.type, file.body)

    return json(upload.metadata)

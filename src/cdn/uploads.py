from sanic import Blueprint, json
from sanic.response import raw

from src.util import status, security
from src.entities import uploads

v1 = Blueprint("v1_uploads", url_prefix="/uploads")


@v1.get("/<upload_id:str>/<token:str>")
async def v1_get_upload(request, upload_id: str, token: str):
    # Get upload
    upload = uploads.get_upload(upload_id)

    # Check token
    if token != upload.token:
        raise status.notFound

    # Get file and check status
    file = upload.file
    if file.status != 0:
        raise status.notFound

    return raw(file.data, content_type=file.mime_type, headers={
        "Content-Disposition": f'inline; filename="{upload.filename}"'
    })


@v1.post("/")
@security.sanic_protected(ignore_suspension=False)
async def v1_create_upload(request):
    # Get file
    file = request.files.get("file")
    if not file:
        raise status.missingPermissions  # placeholder

    # Store file
    upload = uploads.create_upload(request.ctx.user, file.name, file.type, file.body)

    return json(upload.link)

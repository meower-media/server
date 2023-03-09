from sanic import Blueprint, HTTPResponse, json

from src.util import status, security
from src.entities import notifications
from src.database import db

v0 = Blueprint("v0_inbox", url_prefix="/inbox")
v1 = Blueprint("v1_me_inbox", url_prefix="/inbox")


@v0.get("/")
@security.v0_protected()
async def v0_get_notifications(request):
    # Extract page
    page = int(request.args.get("page", 1))
    if page < 1:
        page = 1

    # Fetch and return chat messages
    fetched_notifications = notifications.get_user_notifications(request.ctx.user.id, skip=((page-1)*25), limit=25)
    return json({
        "error": False,
        "autoget": [notification.legacy_client for notification in fetched_notifications],
        "page#": page,
        "pages": ((db.messages.count_documents({"recipient_id": request.ctx.user.id}) // 25)+1)
    })


@v1.get("/")
@security.v1_protected(allow_bots=False, ignore_ban=True)
async def v1_get_notifications(request):
    fetched_notifications = notifications.get_user_notifications(request.ctx.user.id, before=request.args.get("before"),
                                                                 after=request.args.get("after"),
                                                                 limit=int(request.args.get("limit", 25)))
    return json([notification.client for notification in fetched_notifications])


@v1.get("/<notification_id:str>")
@security.v1_protected(allow_bots=False, ignore_ban=True)
async def v1_get_notification(request, notification_id: str):
    notification = notifications.get_notification(notification_id)
    if notification.recipient.id != request.ctx.user.id:
        raise status.resourceNotFound

    return json(notification.client)


@v1.post("/<notification_id:str>/read")
@security.v1_protected(allow_bots=False, ignore_ban=True)
async def v1_mark_notification_as_read(request, notification_id: str):
    notification = notifications.get_notification(notification_id)
    if notification.recipient.id != request.ctx.user.id:
        raise status.resourceNotFound

    notification.mark(True)

    return json(notification.client)


@v1.post("/<notification_id:str>/unread")
@security.v1_protected(allow_bots=False, ignore_ban=True)
async def v1_mark_notification_as_read(request, notification_id: str):
    notification = notifications.get_notification(notification_id)
    if notification.recipient.id != request.ctx.user.id:
        raise status.resourceNotFound

    notification.mark(False)

    return json(notification.client)


@v1.get("/unread")
@security.v1_protected(allow_bots=False, ignore_ban=True)
async def v1_get_unread_notifications(request):
    notification_unread_count = notifications.get_user_notification_unread_count(request.ctx.user.id)
    return json({"count": notification_unread_count})


@v1.delete("/unread")
@security.v1_protected(allow_bots=False, ignore_ban=True)
async def v1_clear_unread_notifications(request):
    notifications.clear_unread_user_notifications(request.ctx.user)
    return HTTPResponse(status=204)

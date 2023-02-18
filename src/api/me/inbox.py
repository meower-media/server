from sanic import Blueprint, HTTPResponse, json

from src.util import status, security
from src.entities import notifications

v1 = Blueprint("v1_me_inbox", url_prefix="/inbox")


@v1.get("/")
@security.sanic_protected(allow_bots=False, ignore_ban=True)
async def v1_get_notifications(request):
    fetched_notifications = notifications.get_user_notifications(request.ctx.user, before=request.args.get("before"),
                                                                 after=request.args.get("after"),
                                                                 limit=int(request.args.get("limit", 25)))
    return json([notification.client for notification in fetched_notifications])


@v1.get("/<notification_id:str>")
@security.sanic_protected(allow_bots=False, ignore_ban=True)
async def v1_get_notification(request, notification_id: str):
    notification = notifications.get_notification(notification_id)
    if notification.recipient.id != request.ctx.user.id:
        raise status.resourceNotFound

    return json(notification.client)


@v1.post("/<notification_id:str>/read")
@security.sanic_protected(allow_bots=False, ignore_ban=True)
async def v1_mark_notification_as_read(request, notification_id: str):
    notification = notifications.get_notification(notification_id)
    if notification.recipient.id != request.ctx.user.id:
        raise status.resourceNotFound

    notification.edit(read=True)

    return HTTPResponse(status=204)


@v1.post("/<notification_id:str>/unread")
@security.sanic_protected(allow_bots=False, ignore_ban=True)
async def v1_mark_notification_as_read(request, notification_id: str):
    notification = notifications.get_notification(notification_id)
    if notification.recipient.id != request.ctx.user.id:
        raise status.resourceNotFound

    notification.edit(read=False)

    return HTTPResponse(status=204)


@v1.get("/unread-count")
@security.sanic_protected(allow_bots=False, ignore_ban=True)
async def v1_get_notification_unread_count(request):
    unread_notifications = notifications.get_user_notification_unread_count(request.ctx.user)
    return json(unread_notifications)


@v1.post("/unread-count/clear")
@security.sanic_protected(allow_bots=False, ignore_ban=True)
async def v1_clear_notification_unread_count(request):
    notifications.clear_unread_user_notifications(request.ctx.user)
    return HTTPResponse(status=204)

from sanic import Blueprint, HTTPResponse, json
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import status
from src.entities import users, accounts, tickets
from src.database import redis

v1 = Blueprint("v1_email", url_prefix="/email")


EMAIL_TICKET_TYPES = set(["password_reset", "email_verification", "email_revert"])


class ResetPasswordForm(BaseModel):
    password: str = Field(
        min_length=8,
        max_length=255
    )


@v1.get("/")
async def v1_get_email_ticket_details(request):
    # Get ticket details
    ticket = tickets.get_ticket_details(request.args.get("ticket"))
    if (not ticket) or (ticket["t"] not in EMAIL_TICKET_TYPES):
        raise status.notAuthenticated

    # Return ticket details
    return json({
        "id": ticket["id"],
        "type": ticket["t"],
        "user": users.get_user(ticket["u"])
    })


@v1.post("/reset-password")
@validate(json=ResetPasswordForm)
async def v1_reset_password(request, body: ResetPasswordForm):
    # Get ticket details
    ticket = tickets.get_ticket_details(request.args.get("ticket"))
    if ticket and (ticket["t"] == "password_reset"):
        account = accounts.get_account(ticket["u"])
    else:
        raise status.notAuthenticated

    # Revoke ticket
    tickets.revoke_ticket(ticket["id"])

    # Set new password
    account.change_password(body.password)

    # Remove account lock
    redis.delete(f"lock:{account.id}")

    return HTTPResponse(status=204)

@v1.post("/verify-email")
async def v1_verify_email(request):
    # Get ticket details
    ticket = tickets.get_ticket_details(request.args.get("ticket"))
    if ticket and (ticket["t"] == "email_verification"):
        account = accounts.get_account(ticket["u"])
    else:
        raise status.notAuthenticated

    # Revoke ticket
    tickets.revoke_ticket(ticket["id"])

    # Set new email
    account.change_email(ticket["email"], require_verification=False)

    return HTTPResponse(status=204)

@v1.post("/revert-email")
async def v1_revert_email(request):
    # Get ticket details
    ticket = tickets.get_ticket_details(request.args.get("ticket"))
    if ticket and (ticket["t"] == "email_revert"):
        account = accounts.get_account(ticket["u"])
    else:
        raise status.notAuthenticated

    # Revoke ticket
    tickets.revoke_ticket(ticket["id"])

    # Set new email
    account.change_email(ticket["email"], require_verification=False, send_email_alert=False)

    return HTTPResponse(status=204)

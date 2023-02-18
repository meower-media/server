from sanic import Blueprint, HTTPResponse, json
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import status, security
from src.entities import sessions, tickets

v1 = Blueprint("v1_me_sessions", url_prefix="/sessions")

class RevokeSessionForm(BaseModel):
    ticket: str = Field(
        max_length=255
    )

@v1.get("/")
@security.sanic_protected(allow_bots=False)
async def v1_get_all_sessions(request):
    return json([session.client for session in sessions.get_all_user_sessions(request.ctx.user)])

@v1.post("/revoke-all")
@validate(json=RevokeSessionForm)
@security.sanic_protected(allow_bots=False)
async def v1_revoke_all_sessions(request, body: RevokeSessionForm):
    sessions.revoke_all_user_sessions(request.ctx.user)

    return HTTPResponse(status=204)

@v1.get("/<session_id:str>")
@security.sanic_protected(allow_bots=False)
async def v1_get_session(request, session_id: str):
    # Get session
    session = sessions.get_user_session(session_id)

    # Check whether session is owned by authenticated user
    if session.user.id != request.ctx.user.id:
        raise status.resourceNotFound
    
    # Return session details
    return json(session.client)

@v1.delete("/<session_id:str>")
@security.sanic_protected(allow_bots=False)
async def v1_revoke_session(request, session_id: str):
    # Get session
    session = sessions.get_user_session(session_id)

    # Check whether session is owned by authenticated user
    if session.user.id != request.ctx.user.id:
        raise status.resourceNotFound
    
    # Revoke session
    session.revoke()

    return HTTPResponse(status=204)

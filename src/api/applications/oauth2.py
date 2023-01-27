from sanic import Blueprint, HTTPResponse, json
from sanic_ext import validate
from pydantic import BaseModel, Field
from typing import Optional

from . import get_application_or_abort_if_not_maintainer, get_application_or_abort_if_not_owner
from src.util import status, security, bitfield, flags
from src.entities import users, tickets

v1 = Blueprint("v1_applications_oauth2", url_prefix="/<application_id:str>/oauth2")

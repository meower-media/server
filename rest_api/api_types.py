from typing import Union

from quart import Quart, Request

import cloudlink
from supporter import Supporter


class AuthenticatedRequest(Request):
    user: Union[str, None] = None
    ip: str


class MeowerQuart(Quart):
    supporter: Supporter
    cl: cloudlink.CloudlinkServer
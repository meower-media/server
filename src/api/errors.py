from sanic import json
from sanic.handlers import ErrorHandler
import os

from src.util import status


class MeowerErrorHandler(ErrorHandler):
    def default(self, request, exception):
        # Try to convert default Sanic errors to Meower errors
        if not (hasattr(exception, "code") and hasattr(exception, "message") and hasattr(exception, "http_status")):
            if os.getenv("DEVELOPMENT", "false") != "true":
                match getattr(exception, "status_code", 500):
                    case 400:
                        exception = status.invalidSyntax
                    case 404:
                        exception = status.endpointNotFound
                    case 500:
                        exception = status.internalServerError
                    case _:
                        exception = status.internalServerError

        return json({
            "error": (exception.code not in [200, 204]),
            "code": exception.code,
            "message": exception.message
        }, status=exception.http_status)

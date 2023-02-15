from sanic import json
from sanic.handlers import ErrorHandler
import os

from src.util import status


class MeowerErrorHandler(ErrorHandler):
    def default(self, request, exception):
        # Try to convert default Sanic errors to Meower errors
        e = exception
        if not (hasattr(e, "error") and hasattr(e, "code") and hasattr(e, "message") and hasattr(e, "http_status")):
            if os.getenv("DEVELOPMENT", "false") != "true":
                match getattr(exception, "status_code", 500):
                    case 400:
                        exception = status.invalidSyntax
                    case 404:
                        exception = status.notFound
                    case 500:
                        exception = status.internal
                    case _:
                        exception = status.internal

        return json({
            "error": exception.error,
            "code": exception.code,
            "message": exception.message
        }, status=exception.http_status)

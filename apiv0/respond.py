import flask
import json

statuses = {
    200: "OK",
    400: "Bad request",
    401: "Not authenticated",
    403: "You do not have permission to access this resource",
    404: "Requested resource not found",
    405: "Resource does not support this method",
    409: "Conflict",
    413: "Payload too large",
    422: "Unprocessable datatype",
    429: "You are being ratelimited",
    500: "Internal server error",
    501: "Not implemented"
}

def respond(status: int, data: dict=None, msg=None, abort=False):
    # Empty response
    if status is None:
        if abort:
            return flask.abort(flask.Response("", status=204))
        else:
            return flask.Response("", status=204)

    # Add data to response
    if data is None:
        data = {}

    # Get status code from statuses dictionary
    if msg is not None:
        status_msg = msg
    elif status not in statuses:
        status_msg = statuses[500]
    else:
        status_msg = statuses[status]

    # Add status message to response
    if status == 200:
        data["ok"] = status_msg
    else:
        data["error"] = status_msg

    # Return response
    if abort:
        return flask.abort(flask.Response(json.dumps(data), content_type="text/json", status=status))
    else:
        return flask.Response(json.dumps(data), content_type="text/json", status=status)
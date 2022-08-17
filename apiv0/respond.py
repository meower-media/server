import flask
import json

with open("apiv0/statuses.json", "r") as f:
    statuses = json.load(f)

def respond(status: str, data: dict=None):
    # Add data to response
    if data is None:
        data = {}

    # Get status code from statuses file
    if status not in statuses:
        status = statuses["general.internal"]
    else:
        status = statuses[status]

    # Add status message to response
    if status["http"] == 200:
        data["ok"] = status["msg"]
    else:
        data["error"] = status["msg"]

    # Return response
    return flask.abort(flask.Response(json.dumps(data), content_type="text/json", status=status["http"]))
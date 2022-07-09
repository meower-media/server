import flask
import json

def respond(resp, status, error=False):
    if (type(resp) == dict) and (type(status) == int) and (type(error) == bool):
        messages = {
            "200": "OK",
            "400": "Bad request",
            "401": "Not authenticated",
            "405": "Method not allowed"
        }
        if "message" not in resp:
            resp["message"] = messages[str(status)]
        resp["error"] = error
        resp["status"] = status
        return flask.abort(flask.Response(response=json.dumps(resp), content_type="text/json", status=status))
    elif (type(status) == int) and (type(error) == bool):
        return flask.abort(flask.Response(response=resp, content_type="text/plain", status=status))
    else:
        return flask.abort(500)
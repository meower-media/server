import flask
import json

def respond(resp, status, error=False):
    if (type(resp) == dict) and (type(status) == int) and (type(error) == bool):
        if "message" not in resp:
            if status == 200:
                resp["message"] = "OK"
            else:
                resp["message"] = None
        resp["error"] = error
        resp["http_status"] = status
        return flask.abort(flask.Response(response=json.dumps(resp), content_type="text/json", status=status))
    elif (type(status) == int) and (type(error) == bool):
        return flask.abort(flask.Response(response=resp, content_type="text/plain", status=status))
    else:
        return respond({"type": "internal", "message": "Internal server error"}, 500, error=True)
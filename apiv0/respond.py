import flask
import json

def respond(resp, status, error=False):
    if (type(resp) == dict) and (type(status) == int) and (type(error) == bool):
        messages = {
            "200": "OK"
        }
        if "message" not in resp:
            resp["message"] = messages[str(status)]
        resp["error"] = error
        resp["status"] = status
        return flask.Response(response=json.dumps(resp), content_type="text/json", status=status)
    elif (type(resp) == str) and (type(status) == int) and (type(error) == bool):
        return flask.Response(response=resp, content_type="text/plain", status=status)
    else:
        flask.abort(500)
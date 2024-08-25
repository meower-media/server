import grpc, time, os
from concurrent import futures

from . import (
    auth_service_pb2_grpc as pb2_grpc,
    auth_service_pb2 as pb2
)

from sentry_sdk import capture_exception

from database import db
from sessions import AccSession


class AuthService(pb2_grpc.AuthServicer):
    def __init__(self, *args, **kwargs):
        pass

    def CheckToken(self, request, context):
        authed = False
        for key, val in context.invocation_metadata():
            if key == "x-token" and val == os.environ["GRPC_AUTH_TOKEN"]:
                authed = True
                break
        if not authed:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing token")

        try:
            username = AccSession.get_username_by_token(request.token)
        except Exception as e:
            capture_exception(e)
        else:
            account = db.usersv0.find_one({"_id": username}, projection={
                "_id": 1,
                "ban.state": 1,
                "ban.expires": 1
            })
            if account and \
                (account["ban"]["state"] == "perm_ban" or \
                (account["ban"]["state"] == "temp_ban" and account["ban"]["expires"] > time.time())):
                account = None

        return pb2.CheckTokenResp(
            valid=(account is not None),
            user_id=(account["_id"] if account else None)
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_AuthServicer_to_server(AuthService(), server)
    server.add_insecure_port(os.environ["GRPC_AUTH_ADDRESS"])
    server.start()
    server.wait_for_termination()

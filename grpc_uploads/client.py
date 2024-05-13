import grpc, os
from . import uploads_service_pb2_grpc as pb2_grpc
from . import uploads_service_pb2 as pb2

channel = grpc.insecure_channel(os.getenv("GRPC_UPLOADS_ADDRESS"))
stub = pb2_grpc.UploadsStub(channel)

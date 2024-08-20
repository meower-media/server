from typing import TypedDict
import os

from grpc_uploads import client as grpc_uploads


class FileDetails(TypedDict):
    id: str
    mime: str
    filename: str
    size: int
    width: int
    height: int


def claim_file(file_id: str, bucket: str) -> FileDetails:
    resp = grpc_uploads.stub.ClaimFile(
        grpc_uploads.pb2.ClaimFileReq(
            id=file_id,
            bucket=bucket
        ),
        metadata=(
            ("x-token", os.getenv("GRPC_UPLOADS_TOKEN")),
        ),
        timeout=30
    )
    return {
        "id": resp.id,
        "mime": resp.mime,
        "filename": resp.filename,
        "size": resp.size,
        "width": resp.width,
        "height": resp.height
    }

def delete_file(file_id: str):
    grpc_uploads.stub.DeleteFile(
        grpc_uploads.pb2.DeleteFileReq(id=file_id),
        metadata=(
            ("x-token", os.getenv("GRPC_UPLOADS_TOKEN")),
        ),
        timeout=30
    )

def clear_files(user_id: str):
    grpc_uploads.stub.ClearFiles(
        grpc_uploads.pb2.ClearFilesReq(user_id=user_id),
        metadata=(
            ("x-token", os.getenv("GRPC_UPLOADS_TOKEN")),
        ),
        timeout=30
    )

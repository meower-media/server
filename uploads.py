from database import db


class FileNotFoundError(Exception): pass
class FileAlreadyClaimedError(Exception): pass


def claim_file(file_id: str, bucket: str, uploader: str):
    # Find file
    file = db.files.find_one()
    if not file:
        raise FileNotFoundError

    result = db.files.update_one({
        "_id": file_id,
        "bucket": bucket,
        "uploaded_by": uploader,
        "claimed": False
    }, {"$set": {"claimed": True}})
    if result.matched_count == 0:
        raise FileNotFoundError
    elif result.modified_count == 0:
        raise FileAlreadyClaimedError

def unclaim_file(file_id: str):
    db.files.update_many(
        {"_id": file_id},
        {"$set": {"claimed": False, "uploaded_at": 0}}
    )

def unclaim_all_files(username: str):
    db.files.update_one(
        {"uploaded_by": username},
        {"$set": {"claimed": False, "uploaded_at": 0}}
    )

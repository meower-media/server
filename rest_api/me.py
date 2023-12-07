from quart import Blueprint, current_app as app, request
import pymongo


me_bp = Blueprint("me_bp", __name__, url_prefix="/me")


@me_bp.get("/reports")
async def get_report_history():
    # Get page
    try:
        page = int(request.args["page"])
    except:
        page = 1

    # Get reports
    reports = list(
        app.files.db.reports.find(
            {"reports.user": request.user},
            projection={"escalated": 0},
            sort=[("reports.time", pymongo.DESCENDING)],
            skip=(page - 1) * 25,
            limit=25,
        )
    )

    # Get reason, comment, and time
    for report in reports:
        for _report in report["reports"]:
            if _report["user"] == request.user:
                report.update({
                    "reason": _report["reason"],
                    "comment": _report["comment"],
                    "time": _report["time"]
                })
        del report["reports"]

    # Get content
    for report in reports:
        if report["type"] == "post":
            report["content"] = app.files.db.posts.find_one(
                {"_id": report.pop("content_id")}, projection={"_id": 1, "u": 1, "isDeleted": 1}
            )
        elif report["type"] == "user":
            report["content"] = app.security.get_account(report.get("content_id"))

    # Return reports
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("reports", {"reports.user": request.user}),
    }
    if "autoget" in request.args:
        payload["autoget"] = reports
    else:
        payload["index"] = [report["_id"] for report in reports]
    return payload, 200

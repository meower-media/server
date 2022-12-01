from flask import Blueprint, request, abort

router = Blueprint("login_router", __name__)

@router.route("/login", methods = ["POST"])
async def login():
    pass

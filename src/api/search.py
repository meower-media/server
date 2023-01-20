from sanic import Blueprint, json
from sanic_ext import validate
from pydantic import BaseModel, Field

from src.util import status
from src.entities import posts

v0 = Blueprint("v0_search", url_prefix="/search")
v1 = Blueprint("v1_search", url_prefix="/search")

@v0.get("/home")
async def v0_search_home(request):
    query = request.args.get("q", "")
    fetched_posts = posts.search_posts(query)
    print(fetched_posts)
    return json({
        "error": False,
        "autoget": [post.legacy for post in fetched_posts],
        "page#": 1,
        "pages": 1,
        "query": {
            "isDeleted": False,
            "p": {
                "$regex": query
            },
            "post_origin": "home"
        }
    })

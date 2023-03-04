from sanic import Blueprint, json

from src.util import security
from src.entities import users, posts

v0 = Blueprint("v0_search", url_prefix="/search")
v1 = Blueprint("v1_search", url_prefix="/search")


@v0.get("/users")
async def v0_search_users(request):
    query = request.args.get("q", "")
    fetched_users = users.search_users(query)
    return json({
        "error": False,
        "autoget": [user.legacy_public for user in fetched_users],
        "page#": 1,
        "pages": 1
    })


@v0.get("/home")
async def v0_search_home(request):
    query = request.args.get("q", "")
    fetched_posts = posts.search_posts(query)
    return json({
        "error": False,
        "autoget": [post.legacy_public for post in fetched_posts],
        "page#": 1,
        "pages": 1
    })


@v1.get("/users")
@security.sanic_protected(require_auth=False, ratelimit_key="search", ratelimit_scope="ip")
async def v1_search_users(request):
    fetched_users = users.search_users(request.args.get("q", ""), before=request.args.get("before"),
                                       after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json([user.partial for user in fetched_users])


@v1.get("/posts")
@security.sanic_protected(require_auth=False, ratelimit_key="search", ratelimit_scope="ip")
async def v1_search_posts(request):
    fetched_posts = posts.search_posts(request.args.get("q", ""), before=request.args.get("before"),
                                       after=request.args.get("after"), limit=int(request.args.get("limit", 25)))
    return json([post.public for post in fetched_posts])

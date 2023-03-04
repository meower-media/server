async def parse_ua(request):
    user_agent = request.headers.get("User-Agent", "Unknown")
    client_name = request.headers.get("X-Client-Name", "Unknown")  # sveltekit_vanilla
    client_version = request.headers.get("X-Client-Version", "Unknown")  # 1.5.1
    client_type = request.headers.get("X-Client-Type", "Unknown")  # desktop/mobile/bot
    request.ctx.user = None
    request.ctx.device = {
        "user_agent": user_agent,
        "client_name": client_name,
        "client_version": client_version,
        "client_type": client_type
    }


async def cors_headers(request, response):
    response.headers.extend({
        "Access-Control-Allow-Methods": "OPTIONS, GET, POST, PATCH, DELETE",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "*"
    })


async def ratelimit_headers(request, response):
    if hasattr(request.ctx, "ratelimit_key"):
        response.headers.extend({
            "X-Ratelimit-Key": request.ctx.ratelimit_key,
            "X-Ratelimit-Scope": request.ctx.ratelimit_scope,
            "X-Ratelimit-Remaining": request.ctx.ratelimit_remaining,
            "X-Ratelimit-Expires": request.ctx.ratelimit_expires
        })

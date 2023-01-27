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

async def ratelimit_header(request, response):
    if hasattr(request.ctx, "ratelimit_bucket"):
        response.headers["X-Ratelimit-Bucket"] = request.ctx.ratelimit_bucket
        response.headers["X-Ratelimit-Remaining"] = request.ctx.ratelimit_remaining
        response.headers["X-Ratelimit-Reset"] = request.ctx.ratelimit_reset

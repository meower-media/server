async def ratelimit_headers(request, response):
    if hasattr(request.ctx, "ratelimit_bucket"):
        response.headers["X-Ratelimit-Bucket"] = request.ctx.ratelimit_bucket
        response.headers["X-Ratelimit-Remaining"] = request.ctx.ratelimit_remaining
        response.headers["X-Ratelimit-Reset"] = request.ctx.ratelimit_reset

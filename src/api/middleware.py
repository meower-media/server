from src.entities import sessions

async def parse_ua(request):
    user_agent = request.headers.get("User-Agent", "Unknown")
    client_name = request.headers.get("X-Client-Name", "Unknown")  # sveltekit_vanilla
    client_version = request.headers.get("X-Client-Version", "Unknown")  # 1.5.1
    client_type = request.headers.get("X-Client-Type", "Unknown")  # desktop/mobile/bot
    request.ctx.device = {
        "user_agent": user_agent,
        "client_name": client_name,
        "client_version": client_version,
        "client_type": client_type
    }

async def authorization(request):
    token = request.headers.get("Authorization")
    if token is None:
        request.ctx.user = None
    else:
        request.ctx.user = sessions.get_user_by_token(token)

def get_ratelimit_id(request):
    if request.ctx.user is None:
        return request.ctx.user.id
    else:
        return request.ip

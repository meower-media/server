from src.cl4.cloudlink import server
from src.cl4.cloudlink.server.protocols import clpv4
from src.cl4.commands import commands

# Initialize the CL server
cl = server()
clpv4 = clpv4(cl)

# Configure the CL server
clpv4.enable_motd = True
clpv4.motd_message = f"Meower Server - Running on CloudLink 4 Server v{cl.version}"
clpv4.real_ip_header = "cf-connecting-ip"
cl.logging.basicConfig(
    level=cl.logging.INFO
)

# Disable default CL commands
disabled = [
    "gmsg",
    "pmsg",
    "gvar",
    "pvar",
    "setid",
    "link",
    "unlink"
]
for method in disabled:
    cl.disable_command(method, clpv4.schema)

# Unbind commands so they can be patched by the commands class
patched = [
    "handshake",
    "direct"
]
for method in patched:
    cl.unbind_command(method, clpv4.schema)

# Set custom CL status codes
clpv4.statuscodes.invalid_token = (clpv4.statuscodes.error, 200, "Invalid token")
clpv4.statuscodes.invalid_subscription_type = (clpv4.statuscodes.error, 201, "Invalid subscription type")
clpv4.statuscodes.session_token_missing = (clpv4.statuscodes.error, 202, "Session token missing")

# Initialize custom dictionaries
cl._users = {}
cl._subscriptions = {
    "new_posts": set(),
    "users": {},
    "posts": {},
    "comments": {},
    "chats": {}
}

# Load custom CL methods
commands(cl, clpv4)

# Initialize the event handler
from src.cl4 import events
@cl.on_connect
async def on_connect(client):
    await events.on_connect(client)

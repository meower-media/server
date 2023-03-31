from src.cl4.cloudlink import server
from src.cl4.cloudlink.server.protocols import clpv4
from src.cl4.commands import CL4Commands

# Initialize the CL server
cl = server()
clpv4 = clpv4(cl)

# Configure the CL server
clpv4.enable_motd = True
clpv4.motd_message = f"Meower Social Media Platform | CL4 Server {cl.version}"
clpv4.real_ip_header = "cf-connecting-ip"

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

# Set custom CL status codes
clpv4.statuscodes.invalid_token = (clpv4.statuscodes.error, 200, "Invalid token")
clpv4.statuscodes.invalid_subscription_type = (clpv4.statuscodes.error, 201, "Invalid subscription type")

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
# cl.load_custom_methods(CL4Commands(cl))

# Initialize the event handler
from src.cl4 import events
@cl.on_connect
async def on_connect(client):
    events.on_connect(client)

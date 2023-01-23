from src.cl4.cloudlink import cloudlink
from src.cl4.commands import CL4Commands

# Initialize the CL server
cl = cloudlink().server(logs=True)

# Configure the CL server
cl.enable_scratch_support = False
cl.check_ip_addresses = True
cl.enable_motd = True
cl.motd_message = "Meower Social Media Platform | CL4 Server"

# Disable default CL commands
cl.disable_methods([
    "gmsg",
    "pmsg",
    "gvar",
    "pvar",
    "setid",
    "link",
    "unlink"
])

# Set custom CL status codes
cl.supporter.codes.update({
    "InvalidToken": (cl.supporter.error, 200, "Invalid token"),
    "InvalidSubscriptionType": (cl.supporter.error, 201, "Invalid subscription type")
})

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
cl.load_custom_methods(CL4Commands(cl))

# Initialize the event handler
from src.cl4 import events
cl.bind_event(cl.events.on_connect, events.on_connect)
cl._event_handler = events

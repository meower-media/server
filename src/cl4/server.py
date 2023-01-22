from src.cl4.cloudlink import cloudlink
from src.cl4.commands import CL4Commands
from src.cl4.events import CL4Events

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
    "InvalidToken": (cl.supporter.error, 1, "Invalid token")
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
cl._event_handler = CL4Events(cl)

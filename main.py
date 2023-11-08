from cloudlink import CloudLink
from supporter import Supporter
from security import Security
from files import Files
from meower import Meower
from rest_api import app as rest_api_app
from threading import Thread
import uvicorn
import os

"""

Meower Social Media Platform - Server Source Code

Dependencies:
* CloudLink >=0.1.7.6
* better-profanity
* bcrypt
* traceback
* datetime
* os
* sys
* json
* random

"""


COMMANDS = {
    # Networking/client utilities
    "ping",
    "get_ulist",

    # Accounts and security
    "authpswd",
    "gen_account",
    "get_profile",
    "accept_terms",
    "update_config",
    "change_pswd",
    "del_tokens",
    "del_account",

    # Group chats/DMs
    "create_chat",
    "leave_chat",
    "get_chat_list",
    "get_chat_data",
    "add_to_chat",
    "remove_from_chat",
    "set_chat_state",

    # Posts
    "get_home",
    "post_home",
    "search_user_posts",
    "get_inbox",
    "get_chat_posts",
    "post_chat",
    "get_post",
    "delete_post",

    # Moderation/administration
    "report"
}


class Main:
    def __init__(self, debug=False):
        # Initalize libraries
        self.cl = CloudLink(debug=debug) # CloudLink Server
        self.supporter = Supporter( # Support functionality
            cl = self.cl,
            packet_callback = self.handle_packet
        )
        self.filesystem = Files( # Filesystem/Database I/O
            logger = self.supporter.log,
            errorhandler = self.supporter.full_stack
        )
        self.supporter.files = self.filesystem
        self.security = Security( # Security and account management
            files = self.filesystem,
            supporter = self.supporter,
            logger = self.supporter.log,
            errorhandler = self.supporter.full_stack
        )
        
        # Initialize Meower
        self.meower = Meower(
            supporter = self.supporter,
            cl = self.cl,
            logger = self.supporter.log,
            errorhandler = self.supporter.full_stack,
            security = self.security,
            files = self.filesystem
        )
        
        # Run REST API
        rest_api_app.cl = self.cl
        rest_api_app.supporter = self.supporter
        rest_api_app.files = self.filesystem
        rest_api_app.security = self.security
        rest_api_app.log = self.supporter.log
        rest_api_thread = Thread(target=uvicorn.run, args=(rest_api_app,), kwargs={
            "host": os.getenv("API_HOST", "0.0.0.0"),
            "port": int(os.getenv("API_PORT", 3001)),
            "root_path": os.getenv("API_ROOT", "")
        })
        rest_api_thread.daemon = True
        rest_api_thread.start()

        # Run background tasks thread
        background_tasks_thread = Thread(target=self.security.run_background_tasks)
        background_tasks_thread.daemon = True
        background_tasks_thread.start()

        # Run CloudLink server
        self.cl.trustedAccess(True, ["meower"])
        self.cl.setMOTD("Meower Social Media Platform Server", True)
        self.cl.server(port=int(os.getenv("CL3_PORT", 3000)), ip=os.getenv("CL3_HOST", ""))
    
    def returnCode(self, client, code, listener_detected, listener_id):
        self.supporter.sendPacket({"cmd": "statuscode", "val": self.cl.codes[str(code)], "id": client}, listener_detected = listener_detected, listener_id = listener_id)
    
    def handle_packet(self, cmd, ip, val, listener_detected, listener_id, client, clienttype):
        try:
            if cmd in COMMANDS:
                getattr(self.meower, cmd)(client, val, listener_detected, listener_id)
            else:
                # Catch-all error code
                self.returnCode(code = "Invalid", client = client, listener_detected = listener_detected, listener_id = listener_id)
        except Exception:
            self.supporter.log("{0}".format(self.supporter.full_stack()))

            # Catch-all error code
            self.returnCode(code = "InternalServerError", client = client, listener_detected = listener_detected, listener_id = listener_id)

if __name__ == "__main__":
    Main(debug=True)
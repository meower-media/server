from cloudlink import CloudLink
from supporter import Supporter
from security import Security
from files import Files
from meower import Meower
from rest_api import app as rest_api_app
from threading import Thread

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
        self.accounts = Security( # Security and account management
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
            accounts = self.accounts,
            files = self.filesystem
        )
        
        # Load trust keys
        result, payload = self.filesystem.load_item("config", "trust_keys")
        if result:
            self.cl.trustedAccess(True, payload["index"])
        
        # Load IP Banlist
        ips = []
        for netlog in self.filesystem.db["netlog"].find({"blocked": True}):
            ips.append(netlog["_id"])
        self.cl.loadIPBlocklist(ips)
        
        # Set server MOTD
        self.cl.setMOTD("Meower Social Media Platform Server", True)
        
        # Run REST API
        Thread(target=rest_api_app.run, kwargs={"host": "0.0.0.0", "port": 3001, "debug": False, "use_reloader": False}).start()

        # Run CloudLink server
        self.cl.server(port=3000, ip="0.0.0.0")
    
    def returnCode(self, client, code, listener_detected, listener_id):
        self.supporter.sendPacket({"cmd": "statuscode", "val": self.cl.codes[str(code)], "id": client}, listener_detected = listener_detected, listener_id = listener_id)
    
    def handle_packet(self, cmd, ip, val, listener_detected, listener_id, client, clienttype):
        try:
            commands = set([
                "ping",
                "version_chk", 
                "get_ulist", 
                "authpswd", 
                "gen_account", 
                "get_profile", 
                "update_config",
                "change_pswd", 
                "del_tokens",
                "del_account",
                "get_home", 
                "get_inbox", 
                "post_home",
                "get_post", 
                "get_peak_users", 
                "search_user_posts",
                "report",
                "close_report",
                "clear_home",
                "clear_user_posts",
                "alert",
                "announce",
                "block",
                "unblock",
                "kick",
                "get_user_ip",
                "get_ip_data",
                "get_user_data",
                "ban",
                "pardon",
                "terminate",
                "impersonate",
                "repair_mode",
                "delete_post",
                "post_chat",
                "set_chat_state",
                "create_chat",
                "leave_chat",
                "get_chat_list",
                "get_chat_data",
                "get_chat_posts",
                "add_to_chat",
                "remove_from_chat"
            ])
            if cmd in commands:
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
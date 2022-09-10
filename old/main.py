from cloudlink import Cloudlink
from supporter import Supporter
from security import Security
from files import Files
from meower import Meower
from rest_api import app as rest_api_app
from threading import Thread

"""

Meower Social Media Platform - Server Source Code

Dependencies:
* CloudLink >=0.1.8.3
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
        self.cl = Cloudlink().server(logs=debug) # CloudLink Server
        self.supporter = Supporter( # Support functionality
            cl = self.cl
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
        self.cl.loadCustomCommands(Meower, {
            Meower: {
                   "supporter": self.supporter,
                   "cl": self.cl,
                   "logger": self.supporter.log,
                   "errorhandler": self.supporter.full_stack,
                   "accounts": self.accounts,
                   "files": self.filesystem
                }
            }
        )
        
        # Load IP Banlist
        ips = []
        for netlog in self.filesystem.db["netlog"].find({"blocked": True}):
            ips.append(netlog["_id"])
        self.cl.ipblocklist = ips
        
        # Set server MOTD
        self.cl.setMOTD("Meower Social Media Platform Server", True)
        
        # Run REST API
        Thread(target=rest_api_app.run, kwargs={"host": "127.0.0.1", "port": 3001, "debug": debug, "use_reloader": False}).start()

        # Run CloudLink server
        self.cl.run(port=3000, host="127.0.0.1")
    
    def returnCode(self, client, code, listener_detected, listener_id):
        self.supporter.sendPacket({"cmd": "statuscode", "val": self.cl.codes[str(code)], "id": client}, listener_detected = listener_detected, listener_id = listener_id)
    
if __name__ == "__main__":
    Main(debug=True)
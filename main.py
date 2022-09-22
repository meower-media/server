from cloudlink import Cloudlink
from threading import Thread
from supporter import Supporter
from accounts import Accounts
from database import Database
from meower import Meower
#from rest_api import app as rest_server
from dotenv import load_dotenv
from datetime import datetime
import uuid
import time

class Server:
    
    """
    Meower Server
    
    This is the source code for a complete, standalone Meower server.
    This depends upon a running instance of MongoDB.
    
    Meower's Python dependencies are:
    * cloudlink >= 0.1.8.7
    * websockets
    * flask
    * flask_cors
    * better-profanity
    * bcrypt 
    
    These dependencies are built-in to Python.
    * threading
    * traceback
    * datetime
    * time
    * os
    * sys
    * json
    * random
    
    In a production environment, you should forward ports 3000 and 3001
    using a reverse proxy or a tunneling service (ex. ngrok, cloudflare).
    
    If you are running Meower in a Python container (ex. Docker or Podman),
    set the ip parameter to 0.0.0.0 to expose the container to the network
    and to your reverse proxy/tunneling daemon(s).
    
    Under no circumstance should you port forward the server directly,
    this is a security risk, and Cloudlink does not have native support
    for TLS/SSL.
    """
    
    def __init__(self, ip:str = "127.0.0.1", db_ip:str = "mongodb://192.168.86.40:27017", debug:bool = False):
    
        # Load environment variables from the .env file
        load_dotenv()
        
        self.uuid = uuid
        self.datetime = datetime
        self.time = time.time
        
        # Initialize the Cloudlink server.
        self.cl = Cloudlink().server(
            logs = debug
        )
        
        # Create shared log attribute from Cloudlink's native logging functionality
        self.log = self.cl.supporter.log
        
        # Set the server's Message-Of-The-Day.
        self.cl.setMOTD(True, "Meower Social Media Platform Server")
        
        # Disable commands for Cloudlink, as this functionality is handled by the Meower server
        self.cl.disableCommands(
            [
                "setid",
                "link", 
                "unlink"
            ]
        )
        
        # Meower libraries will inherit cl from self, as well as inherit each other from self
        self.supporter = Supporter(self)
        self.db = Database(self, db_ip)
        self.accounts = Accounts(self)
        
        # Initialize the Meower server and it's commands, and allow Meower to access self, see the Meower class for more info.
        self.cl.loadCustomCommands(
            Meower, 
            {
                Meower: self
            }
        )
        
        # Load blocklist
        self.cl.ipblocklist = list(
            self.db.dbclient["netlog"].find(
                {
                    "blocked": True
                }
            )
        )
        
        # Run REST API
        """Thread(
            target = rest_server.run,
            kwargs = {
                "host": ip,
                "port": 3001,
                "debug": debug,
                "use_reloader": False
            }
        ).start()"""
        
        # Run Cloudlink server
        self.cl.run(host = ip, port = 3000)
        exit()

if __name__ == "__main__":
    Server(
        ip = "127.0.0.1",
        debug = True
    )
from cloudlink import Cloudlink
from threading import Thread
from supporter import Supporter
<<<<<<< Updated upstream
from security import Security
from database import Database
from meower import Meower
from rest_api import app as rest_server
=======
from accounts import Accounts
from database import Database
from meower import Meower
#from rest_api import app as rest_server
from dotenv import load_dotenv
from datetime import datetime
import uuid
import time
>>>>>>> Stashed changes

class Server:
    
    """
    Meower Server
    
    This is the source code for a complete, standalone Meower server.
    This depends upon a running instance of MongoDB.
    
    Meower's Python dependencies are:
<<<<<<< Updated upstream
    * cloudlink >= 0.1.8.4
    * websocket-client (should be bundled with cloudlink)
    * websocket-server (should be bundled with cloudlink)
=======
    * cloudlink >= 0.1.8.7
    * websockets
>>>>>>> Stashed changes
    * flask
    * flask_cors
    * better-profanity
    * bcrypt 
    
    These dependencies are built-in to Python.
    * threading
    * traceback
    * datetime
<<<<<<< Updated upstream
=======
    * time
>>>>>>> Stashed changes
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
    
<<<<<<< Updated upstream
    def __init__(self, ip:str = "127.0.0.1", debug:bool = False):
=======
    def __init__(self, ip:str = "127.0.0.1", db_ip:str = "mongodb://192.168.86.40:27017", debug:bool = False):
    
        # Load environment variables from the .env file
        load_dotenv()
        
        self.uuid = uuid
        self.datetime = datetime
        self.time = time.time
        
>>>>>>> Stashed changes
        # Initialize the Cloudlink server.
        self.cl = Cloudlink().server(
            logs = debug
        )
        
        # Create shared log attribute from Cloudlink's native logging functionality
        self.log = self.cl.supporter.log
        
        # Set the server's Message-Of-The-Day.
<<<<<<< Updated upstream
        cl.setMOTD(
            True,
            "Meower Media Co. Homeserver - If you aren't a Meower / Meower-compatible client, you probably shouldn't be here!"
        )
        
        # Disable commands for Cloudlink, as this functionality is handled by the Meower server
        cl.disableCommands(
=======
        self.cl.setMOTD(True, "Meower Social Media Platform Server")
        
        # Disable commands for Cloudlink, as this functionality is handled by the Meower server
        self.cl.disableCommands(
>>>>>>> Stashed changes
            [
                "setid",
                "link", 
                "unlink"
            ]
        )
        
        # Meower libraries will inherit cl from self, as well as inherit each other from self
        self.supporter = Supporter(self)
<<<<<<< Updated upstream
        self.db = Database(self)
        self.security = Security(self)
        
        # Initialize the Meower server and it's commands, and allow Meower to access self, see the Meower class for more info.
        cl.loadCustomCommands(
=======
        self.db = Database(self, db_ip)
        self.accounts = Accounts(self)
        
        # Initialize the Meower server and it's commands, and allow Meower to access self, see the Meower class for more info.
        self.cl.loadCustomCommands(
>>>>>>> Stashed changes
            Meower, 
            {
                Meower: self
            }
        )
        
        # Load blocklist
<<<<<<< Updated upstream
        cl.ipblocklist = list(
            self.db["netlog"].find(
=======
        self.cl.ipblocklist = list(
            self.db.dbclient["netlog"].find(
>>>>>>> Stashed changes
                {
                    "blocked": True
                }
            )
        )
        
        # Run REST API
<<<<<<< Updated upstream
        Thread(
            target=rest_server.run,
            kwargs={
=======
        """Thread(
            target = rest_server.run,
            kwargs = {
>>>>>>> Stashed changes
                "host": ip,
                "port": 3001,
                "debug": debug,
                "use_reloader": False
            }
<<<<<<< Updated upstream
        ).start()
        
        # Run Cloudlink server
        cl.run(
            host = ip,
            port = 3000
        )
=======
        ).start()"""
        
        # Run Cloudlink server
        self.cl.run(host = ip, port = 3000)
        exit()
>>>>>>> Stashed changes

if __name__ == "__main__":
    Server(
        ip = "127.0.0.1",
        debug = True
    )
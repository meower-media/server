# Cloudlink
from cloudlink import cloudlink
from accounts import accounts
from database import database
from supporter import supporter
from meower import meower

# REST API
from rest_api.errors import router as errors_bp
from rest_api.middleware import router as middleware_bp
from rest_api.auth import router as auth_bp

# Pip
import secrets
from dotenv import load_dotenv
import uuid
import threading
from datetime import datetime
from time import time
from quart import Quart

# Load env variables
load_dotenv()

class main:
    def __init__(self, db_ip:str = "mongodb://127.0.0.1:27017", timeout_ms:int = 10000, debug:bool = False):
        # Initialize CL4 server
        self.server = cloudlink().server(logs=debug)

        # Configure the CL4 server
        self.server.enable_scratch_support = False
        self.server.check_ip_addresses = True
        self.server.enable_motd = True
        self.server.motd_message = "Meower Social Media Platform Server"

        # Disable specific CL commands
        self.server.disable_methods(["setid"])
        
        # Create alias for builtin functions
        self.log = self.server.supporter.log
        self.uuid = uuid
        self.datetime = datetime
        self.time = time

        # Initialize libraries
        self.supporter = supporter(self)
        self.db = database(self, db_ip, timeout_ms)
        self.accounts = accounts(self)
        self.meower = meower(self)

        # Load Meower CL4 methods - Will automatically override builtin commands
        self.server.load_custom_methods(self.meower)
    
    def run(self, host:str = "127.0.0.1", cl_port:int = 3000, api_port:int = 3001):   
        # Run REST API
        rest_api = Quart(__name__, root_path = "/v0")
        rest_api.register_blueprint(errors_bp)
        rest_api.register_blueprint(middleware_bp)
        rest_api.register_blueprint(auth_bp, url_prefix = "/auth")
        rest_api_thread = threading.Thread(target=rest_api.run, kwags={"host": host, "port": api_port})
        rest_api_thread.daemon = True
        rest_api_thread.start()

        # Run Cloudlink server
        self.server.run(host, cl_port)
    
    def run_cl_only(self, host:str = "127.0.0.1", cl_port:int = 3000):
        self.server.run(host, cl_port)

if __name__ == "__main__":
    meowerserver = main(db_ip="mongodb://192.168.1.185:27017/", debug=True) # Local IP
    meowerserver.run_cl_only()
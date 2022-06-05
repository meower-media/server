from meower import Meower
from ext.websocket import WS
from ext.supporter import Supporter
from ext.security import Security
from ext.files import Files
from ext.posts import Posts
from ext.rest_api import REST_API

"""

Meower Social Media Platform - Server Source Code

Dependencies:
* better-profanity
* bcrypt
* uuid
* flask
* flask_cors
* pymongo

"""

class Main:
    def __init__(self, debug=False):
        # Create main Meower class
        self.meower = Meower
        self.meower.version = "0.1.0"

        # Add modules to Meower class
        self.meower.supporter = Supporter(self.meower)
        self.meower.files = Files(self.meower)
        self.meower.accounts = Security(self.meower)
        self.meower.posts = Posts(self.meower)
        self.meower.ws = WS()
        self.meower.rest_api = REST_API

        self.meower.log = self.meower.supporter.log
        self.meower.full_stack = self.meower.supporter.full_stack
        self.meower.timestamp = self.meower.supporter.timestamp

        # Initialize class to start everything
        self.meower()

if __name__ == "__main__":
    Main()
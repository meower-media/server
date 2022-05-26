from meower import Meower
from ext.cloudlink import CloudLink
from ext.commands import WSCommands
from ext.supporter import Supporter
from ext.security import Security
from ext.files import Files
from ext.posts import Posts
from ext.chats import Chats
from ext.rest_api import REST_API

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
        # Create main Meower class
        self.meower = Meower
        self.meower.debug = debug
        self.meower.version = "0.1.0"

        # Add command handler to Meower class
        self.meower.packet_callback = self.meower.run_ws_command

        # Add modules to Meower class
        self.meower.cl = CloudLink(debug=debug)
        self.meower.supporter = Supporter(self.meower)
        self.meower.files = Files(self.meower)
        self.meower.accounts = Security(self.meower)
        self.meower.posts = Posts(self.meower)
        self.meower.chats = Chats(self.meower)
        self.meower.commands = WSCommands(self.meower)

        # Add REST API to Meower class
        self.meower.rest_api = REST_API

        # Initialize class to start everything
        self.meower()

if __name__ == "__main__":
    Main(debug=True)

from cloudlink import CloudLink
from supporter import Supporter
from security import Security
from files import Files
from meower import Meower

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
        result, payload = self.filesystem.load_item("config", "IPBanlist")
        if result:
            self.cl.loadIPBlocklist(payload["wildcard"])
        
        # Set server MOTD
        self.cl.setMOTD("Meower Social Media Platform Server", True)
        
        # Run server
        self.cl.server(port=3000, ip="0.0.0.0")
    
        self.meower.createPost(post_origin="inbox", user="tnix_alt", content={"h": "Moderator Alert", "p": "Message from a moderator: test alert"})
        self.meower.createPost(post_origin="inbox", user="tnix_alt", content={"h": "Account Alert", "p": "Your account was about to be deleted but you logged in! Your account has been restored. If you weren't the one to request your account to be deleted, please change your password immediately."})
        self.meower.createPost(post_origin="inbox", user="tnix_alt", content={"h": "New Love", "p": "test new love"})
        self.meower.createPost(post_origin="inbox", user="tnix_alt", content={"h": "New Meow", "p": "test new love"})
        self.meower.createPost(post_origin="inbox", user="tnix_alt", content={"h": "Notification", "p": "You have been added to the group chat 'alt_home'!"})
        self.meower.createPost(post_origin="inbox", user="tnix_alt", content={"h": "Announcement", "p": "test new announcement"})

    def returnCode(self, client, code, listener_detected, listener_id):
        self.supporter.sendPacket({"cmd": "statuscode", "val": self.cl.codes[str(code)], "id": client}, listener_detected = listener_detected, listener_id = listener_id)
    
    def handle_packet(self, cmd, ip, val, listener_detected, listener_id, client, clienttype):
        try:
            # Meower's Packet Interpreter goes here. All Requests to the server are handled here.
            if cmd == "ping":
                # Network heartbeat
                self.meower.ping(client, listener_detected, listener_id)
            elif cmd == "version_chk":
                # Check client versions
                self.meower.version_chk(client, val, listener_detected, listener_id)
            elif cmd == "authpswd":
                # Authenticate client
                self.meower.authpswd(client, val, listener_detected, listener_id)
            elif cmd == "gen_account":
                # Authenticate client
                self.meower.gen_account(client, val, listener_detected, listener_id)
            elif cmd == "get_profile":
                # Get user profile data
                self.meower.get_profile(client, val, listener_detected, listener_id)
            elif cmd == "update_config":
                # Update client settings
                self.meower.update_config(client, val, listener_detected, listener_id)
            elif cmd == "del_account":
                # Delete user account
                self.meower.del_account(client, listener_detected, listener_id)
            elif cmd == "get_home":
                # Get homepage index
                self.meower.get_home(client, val, listener_detected, listener_id)
            elif cmd == "get_inbox":
                # Get inbox posts
                self.meower.get_inbox(client, val, listener_detected, listener_id)
            elif cmd == "get_announcements":
                # Get announcement posts
                self.meower.get_announcements(client, val, listener_detected, listener_id)
            elif cmd == "post_home":
                # Create post for homepage
                self.meower.post_home(client, val, listener_detected, listener_id)
            elif cmd == "get_post":
                # Get post from homepage
                self.meower.get_post(client, val, listener_detected, listener_id)
            elif cmd == "get_peak_users":
                # Get current peak # of users data
                self.meower.get_peak_users(client, listener_detected, listener_id)
            elif cmd == "search_user_posts":
                # Get user's posts
                self.meower.search_user_posts(client, val, listener_detected, listener_id)
            elif cmd == "search_home_posts":
                # Get home post by query
                self.meower.search_home_posts(client, val, listener_detected, listener_id)
            elif cmd == "search_profiles":
                # Get profiles by query
                self.meower.search_profiles(client, val, listener_detected, listener_id)
            elif cmd == "clear_home":
                # Clear a page of home
                self.meower.clear_home(client, val, listener_detected, listener_id)
            elif cmd == "clear_user_posts":
                # Clear all of a user's posts
                self.meower.clear_user_posts(client, val, listener_detected, listener_id)
            elif cmd == "alert":
                # Send alert to a user
                self.meower.alert(client, val, listener_detected, listener_id)
            elif cmd == "announce":
                # Send global announcement
                self.meower.announce(client, val, listener_detected, listener_id)
            elif cmd == "block":
                # Block IP address (wildcard mode)
                self.meower.block(client, val, listener_detected, listener_id)
            elif cmd == "unblock":
                # Unblock IP address (wildcard mode)
                self.meower.unblock(client, val, listener_detected, listener_id)
            elif cmd == "kick":
                # Kick users
                self.meower.kick(client, val, listener_detected, listener_id)
            elif cmd == "get_user_ip":
                # Get user IP addresses
                self.meower.get_user_ip(client, val, listener_detected, listener_id)
            elif cmd == "get_ip_data":
                # Return netlog data of an IP
                self.meower.get_ip_data(client, val, listener_detected, listener_id)
            elif cmd == "get_user_data":
                # Return full account data (excluding password hash)
                self.meower.get_user_data(client, val, listener_detected, listener_id)
            elif cmd == "ban":
                # Ban users
                self.meower.ban(client, val, listener_detected, listener_id)
            elif cmd == "pardon":
                # Pardon users
                self.meower.pardon(client, val, listener_detected, listener_id)
            elif cmd == "ip_ban":
                # Ban IPs
                self.meower.ip_ban(client, val, listener_detected, listener_id)
            elif cmd == "ip_pardon":
                # Pardon IPs
                self.meower.ip_pardon(client, val, listener_detected, listener_id)
            elif cmd == "terminate":
                # Terminate users
                self.meower.terminate(client, val, listener_detected, listener_id)
            elif cmd == "repair_mode":
                # Enable repair mode
                self.meower.repair_mode(client, listener_detected, listener_id)
            elif cmd == "delete_post":
                # Delete posts
                self.meower.delete_post(client, val, listener_detected, listener_id)
            elif cmd == "post_chat":
                # Post chat
                self.meower.post_chat(client, val, listener_detected, listener_id)
            elif cmd == "set_chat_state":
                # Set chat state
                self.meower.set_chat_state(client, val, listener_detected, listener_id)
            elif cmd == "create_chat":
                # Create group chat
                self.meower.create_chat(client, val, listener_detected, listener_id)
            elif cmd == "leave_chat":
                # Leave group chat
                self.meower.leave_chat(client, val, listener_detected, listener_id)
            elif cmd == "get_chat_list":
                # Get group chat list
                self.meower.get_chat_list(client, listener_detected, listener_id)
            elif cmd == "get_chat_data":
                # Get group chat data
                self.meower.get_chat_data(client, val, listener_detected, listener_id)
            elif cmd == "get_chat_posts":
                # Get group chat posts
                self.meower.get_chat_posts(client, val, listener_detected, listener_id)
            elif cmd == "add_to_chat":
                # Add someone to group chat
                self.meower.add_to_chat(client, val, listener_detected, listener_id)
            elif cmd == "remove_from_chat":
                # Remove someone from group chat
                self.meower.remove_from_chat(client, val, listener_detected, listener_id)
            
            # Lol whitespace for future code

            else:
                # Catch-all error code
                self.returnCode(code = "Invalid", client = client, listener_detected = listener_detected, listener_id = listener_id)
        except Exception:
            self.supporter.log("{0}".format(self.supporter.full_stack()))

if __name__ == "__main__":
    Main(debug=True)

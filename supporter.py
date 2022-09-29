from better_profanity import profanity
import string
import copy

class Supporter:
    
    """
    Meower Supporter
    
    This class provides shared functionality between the Meower,
    Security, and Database classes.
    """
    
    def __init__(self, parent):
        # Inherit parent class attributes
        self.parent = parent
        self.log = parent.log
        self.full_stack = parent.cl.supporter.full_stack
        self.datetime = parent.datetime
        self.time = parent.time
        
        # Inherit cloudlink from parent class, since custom info/error codes are needed
        self.cloudlink = parent.cl
        
        # Set up attributes
        self.filter = None
        self.parent.repair_mode = False
        self.parent.is_scratch_deprecated = False
        self.profanity = profanity
        
        # Add custom status codes to CloudLink
        self.cloudlink.supporter.codes["KeyNotFound"] = "I:010 | Key Not Found"
        self.cloudlink.supporter.codes["PasswordInvalid"] = "I:011 | Invalid Password"
        self.cloudlink.supporter.codes["GettingReady"] = "I:012 | Getting ready"
        self.cloudlink.supporter.codes["ObsoleteClient"] = "I:013 | Client is out-of-date or unsupported"
        self.cloudlink.supporter.codes["IDExists"] = "I:015 | Account exists"
        self.cloudlink.supporter.codes["2FAOnly"] = "I:016 | 2FA Required"
        self.cloudlink.supporter.codes["MissingPermissions"] = "I:017 | Missing permissions"
        self.cloudlink.supporter.codes["Banned"] = "E:018 | Account Banned"
        self.cloudlink.supporter.codes["IllegalChars"] = "E:019 | Illegal characters detected"
        self.cloudlink.supporter.codes["Kicked"] = "E:020 | Kicked"
        self.cloudlink.supporter.codes["ChatExists"] = "E:021 | Chat exists"
        self.cloudlink.supporter.codes["ChatNotFound"] = "E:022 | Chat not found"
        self.cloudlink.supporter.codes["RateLimit"] = "E:023 | Ratelimit"
        self.cloudlink.supporter.codes["TooLarge"] = "E:024 | Data too large"
        self.cloudlink.supporter.codes["MemberExists"] = "E:025 | Member already exists in chat"
        self.cloudlink.supporter.codes["MemberDoesNotExist"] = "E:026 | Member does not exist in chat"
        
        # Create permitted lists of characters
        self.permitted_chars_username = []
        self.permitted_chars_post = []
        for char in string.ascii_letters:
            self.permitted_chars_username.append(char)
            self.permitted_chars_post.append(char)
        for char in string.digits:
            self.permitted_chars_username.append(char)
            self.permitted_chars_post.append(char)
        for char in string.punctuation:
            self.permitted_chars_post.append(char)
        self.permitted_chars_username.extend(["_", "-"])
        self.permitted_chars_post.append(" ")
        
        # Peak number of users logger
        self.peak_users_logger = {
            "count": 0,
            "timestamp": self.timestamp(1),
            "epoch": self.timestamp(7)
        }
        
        # Specify server callbacks
        self.cloudlink.callback(parent.cl.on_close, self.on_close)
        self.cloudlink.callback(parent.cl.on_connect, self.on_connect)
        
        self.log("Meower supporter initialized!")
    
    async def on_close(self, client):
        self.log(f"{client.id} Disconnected.")
        if client.authed:
            # Session management
            if client.id in self.parent.user_sessions[client.friendly_username]:
                self.parent.user_sessions[client.friendly_username].remove(client.id)
            online = (len(self.parent.user_sessions[client.friendly_username]) != 0)
            
            # Update the account state
            args = {
                "last_ip": client.full_ip,
                "online": online
            }
            
            self.parent.accounts.update_setting(
                client.friendly_username,
                args,
                forceUpdate = True
            )
            
            # Tell all clients that someone is no longer online
            if not online:
                for client_tmp in copy.copy(self.cloudlink.all_clients):
                    if not client_tmp == client:
                        await self.cloudlink.sendPacket(
                            client_tmp,
                            {
                                "cmd": "direct",
                                "val": {
                                    "mode": "offline",
                                    "username": client.friendly_username
                                }
                            },
                            ignore_rooms = True)
    
    async def on_connect(self, client):
        # Create attributes for the new client
        client.authtype = ""
        client.authed = False
        client.last_packet = {}
        client.burst_amount = {}
        client.ratelimit = {}
        client.linked_chat = None
        client.session_token = None
        
        # TODO: Verify that the client's IP is not a VPN/Proxy
    
    async def autoID(self, client, username, listener_detected:bool = False, listener_id:str = "", extra_data:dict = None, echo:bool = False):
        # Set the client's username, however CL4 does not report back to the user by default.
        self.cloudlink.setClientUsername(client, username)
        # Manually report to the client that it has been given a username
        msg = {
            "username": client.friendly_username,
            "id": client.id
        }
        if extra_data:
            for key in extra_data.keys():
                msg[key] = extra_data[key]
        if echo:
            await self.cloudlink.sendCode(client, "OK", listener_detected, listener_id, msg)
        await self.log_peak_users()
    
    async def log_peak_users(self):
        current_users = len(self.cloudlink.all_clients)
        if current_users > self.peak_users_logger["count"]:
            self.peak_users_logger = {
                "count": current_users,
                "timestamp": self.timestamp(1),
                "epoch": self.timestamp(7)
            }
            self.log("New peak in # of concurrent users: {0}".format(current_users))
            #self.create_system_message("Yay! New peak in # of concurrent users: {0}".format(current_users))
            for client in self.cloudlink.getAllUsersInRoom("default"):
                await self.cloudlink.sendPacket(
                    client,
                    {
                        "cmd": "direct",
                        "val": {
                            "mode": "peak",
                            "payload": self.peak_users_logger
                        }
                    }
                )
    
    def timestamp(self, ttype):
        today = self.datetime.now()
        match ttype:
            case 1:
                return {
                    "mo": today.strftime("%m"),
                    "d": today.strftime("%d"),
                    "y": today.strftime("%Y"),
                    "h": today.strftime("%H"),
                    "mi": today.strftime("%M"),
                    "s": today.strftime("%S"),
                    "e": (int(self.time()))
                }
            case 2:
                return str(today.strftime("%H%M%S"))
            case 3:
                return str(today.strftime("%d%m%Y%H%M%S"))
            case 4:
                return today.strftime("%m/%d/%Y %H:%M.%S")
            case 5:    
                return today.strftime("%d%m%Y")
            case 6:
                return int(self.time() // 1)
            case 7:
                return self.time()
            case _: # Default behavior when a case match does not exist
                self.parent.panic_exception_counter += 1
                raise NotImplementedError
    
    def ratelimit(self, client):
        # Guard clause for checking if a client exists
        if not client in self.cloudlink.all_clients:
            return
        client.last_packet = int(self.time())
    
    def wordfilter(self, message):
        # Word censor
        self.profanity.load_censor_words()
        
        # Guard clause for checking if the filter is loaded
        if self.filter == None:
            self.log("Failed loading profanity filter : Using default filter as fallback")
            return self.profanity.censor(message)
        
        self.profanity.load_censor_words(
            whitelist_words = self.filter["whitelist"]
        )
        self.profanity.add_censor_words(self.filter["blacklist"])
        
        message = self.profanity.censor(message)
        return message
    
    def checkForBadCharsUsername(self, value):
        # Check for profanity in username, will return '*' if there's profanity which will be blocked as an illegal character
        value = self.wordfilter(value)
        
        for char in value:
            if not char in self.permitted_chars_username:
                return True
        return False
    
    def checkForBadCharsPost(self, value):
        for char in value:
            if not char in self.permitted_chars_post:
                return True
        return False
    
    def kickUser(self, client, status="Kicked"):
        # Guard clause for checking if a client exists
        if not client in self.cloudlink.all_clients:
            return
        self.log("Kicking {0}".format(client.friendly_username))

        # Tell client it's going to get kicked
        self.cloudlink.sendCode(client, self.cloudlink.supporter.codes[status])
        
        # Terminate client
        self.rejectClient(client, "Client was kicked by the server")
    
    def check_for_spam(self, type, client, burst=1, seconds=1):
        # Check if a client exists
        if not client in self.cloudlink.all_clients:
            return False
        
        # Check if client has attribute dict keys
        if not type in client.last_packet:
            client.last_packet[type] = 0
            client.burst_amount[type] = 0
            client.ratelimit[type] = 0
        
        # Check if user is currently ratelimited
        if client.ratelimit[type] > self.time():
            return True

        # Check if max burst has expired
        if (client.last_packet[type] + seconds) < self.time():
            client.burst_amount[type] = 0

        # Set last packet time and add to burst amount
        client.last_packet[type] = self.time()
        client.burst_amount[type] += 1

        # Check if burst amount is over max burst
        if client.burst_amount[type] > burst:
            client.ratelimit[type] = (self.time() + seconds)
            client.burst_amount[type] = 0
            return True
        else:
            return False
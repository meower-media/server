from better_profanity import profanity
import string
import copy

class supporter:
    
    """
    Meower Supporter - CL4 Port compliant
    
    This class provides shared functionality between the Meower,
    Security, and Database classes.
    """
    
    def __init__(self, parent):
        # Inherit parent class attributes
        self.parent = parent
        self.log = parent.log
        self.full_stack = parent.server.supporter.full_stack
        self.datetime = parent.datetime
        self.time = parent.time
        self.server = parent.server
        self.clients = parent.server.clients
        
        # Set up attributes
        self.filter = None
        self.parent.repair_mode = False
        self.parent.is_scratch_deprecated = False
        self.profanity = profanity
        
        # Add custom status codes to CloudLink
        self.info = "I"
        self.error = "E"
        meower_codes = {
            "KeyNotFound": (self.info, 10, "Key Not Found"),
            "PasswordInvalid": (self.info, 11, "Invalid Password"),
            "GettingReady": (self.info, 12, "Getting ready"),
            "ObsoleteClient": (self.info, 13, "Client is out-of-date or unsupported"),
            "IDExists": (self.info, 15, "Account exists"),
            "2FAOnly": (self.info, 16, "2FA Required"),
            "MissingPermissions": (self.info, 17, "Missing permissions"),
            "Banned": (self.error, 18, "Account Banned"),
            "IllegalChars": (self.error, 19, "Illegal characters detected"),
            "Kicked": (self.error, 20, "Kicked"),
            "ChatExists": (self.error, 21, "Chat exists"),
            "ChatNotFound": (self.error, 22, "Chat not found"),
            "RateLimit": (self.error, 23, "Ratelimit"),
            "MemberExists": (self.error, 25, "Member already exists in chat"),
            "MemberDoesNotExist": (self.error, 26, "Member does not exist in chat"),
            "Blocked": (self.error, 27, "IP address blocked"),
            "NoProxyVPNBlock": (self.error, 28, "IP address blocked: VPNs/Proxies are not permitted")
        }
        self.server.supporter.codes.update(meower_codes)
        
        # Create permitted lists of characters
        self.permitted_chars_username = set()
        self.permitted_chars_post = set()
        for char in string.ascii_letters:
            self.permitted_chars_username.add(char)
            self.permitted_chars_post.add(char)
        for char in string.digits:
            self.permitted_chars_username.add(char)
            self.permitted_chars_post.add(char)
        for char in string.punctuation:
            self.permitted_chars_post.add(char)
        self.permitted_chars_username.add("_")
        self.permitted_chars_username.add("-")
        self.permitted_chars_post.add(" ")
        
        # Peak number of users logger
        self.peak_users_logger = {
            "count": 0,
            "timestamp": self.timestamp(1),
            "epoch": self.timestamp(7)
        }
        
        self.log("[Meower supporter] Meower supporter initialized!")
    
    async def auto_id(self, client, username, listener:str = None, extra_data:dict = None, echo:bool = False):
        # Set the client's username, however CL4 does not report back to the user by default.
        self.server.set_client_username(client, username)
        # Manually report to the client that it has been given a username
        msg = {
            "val": {
                "username": client.friendly_username,
                "id": client.id
            }
        }
        if extra_data:
            msg["val"].update(extra_data)
        if echo:
            # Template for updated send_code command
            await self.server.send_code(
                client = client,
                code = "OK",
                extra_data = msg,
                listener = listener
            )
        await self.log_peak_users()
    
    async def log_peak_users(self):
        current_users = len(self.server.clients.get_all_cloudlink())
        if current_users > self.peak_users_logger["count"]:
            self.peak_users_logger = {
                "count": current_users,
                "timestamp": self.timestamp(1),
                "epoch": self.timestamp(7)
            }
            self.log("[Meower supporter] New peak in # of concurrent users: {0}".format(current_users))
            #self.create_system_message("Yay! New peak in # of concurrent users: {0}".format(current_users))
            
            await self.server.send_packet_multicast(
                cmd = "direct",
                val = {
                    "mode": "peak",
                    "payload": self.peak_users_logger
                },
                clients = self.server.clients.get_all_cloudlink()
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
        if not client in self.server.all_clients:
            return
        client.last_packet = int(self.time())
    
    def wordfilter(self, message):
        # Word censor
        self.profanity.load_censor_words()
        
        # Guard clause for checking if the filter is loaded
        if self.filter == None:
            self.log("[Meower supporter] Failed loading profanity filter: Using default filter as fallback")
            return self.profanity.censor(message)
        
        self.profanity.load_censor_words(
            whitelist_words = self.filter["whitelist"]
        )
        self.profanity.add_censor_words(self.filter["blacklist"])
        
        message = self.profanity.censor(message)
        return message
    
    def check_for_bad_chars_username(self, value):
        # Check for profanity in username, will return '*' if there's profanity which will be blocked as an illegal character
        value = self.wordfilter(value)
        
        for char in value:
            if not char in self.permitted_chars_username:
                return True
        return False
    
    def check_for_bad_chars_post(self, value):
        for char in value:
            if not char in self.permitted_chars_post:
                return True
        return False
    
    async def kick_user(self, client, status="Kicked"):
        # Guard clause for checking if a client exists
        if not client in self.server.clients.get_all_cloudlink():
            return
        self.log("[Meower supporter] Kicking {0}".format(client.friendly_username))

        # Tell client it's going to get kicked
        await self.server.send_code(client, status)
        
        # Terminate client
        await self.server.reject_client(client, "Client was kicked by the server")
    
    def check_for_spam(self, type, client, burst=1, seconds=1):
        # Check if a client exists
        if not client in self.server.clients.get_all_cloudlink():
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
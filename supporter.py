from dotenv import load_dotenv
from better_profanity import profanity
from datetime import datetime

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
        
        # Inherit cloudlink from parent class, since custom info/error codes are needed
        self.cl = parent.cl
        
        # Set up attributes for the supporter class
        self.filter = None
        self.last_packet = {}
        self.burst_amount = {}
        self.ratelimits = {}
        self.good_ips = []
        self.known_vpns = []
        self.status = {"repair_mode": True, "is_deprecated": False}
        self.profanity = profanity
        
		# Load environment variables from the .env file
        load_dotenv()
        
        # Add custom status codes to CloudLink
        self.cl.supporter.codes["KeyNotFound"] = "I:010 | Key Not Found"
        self.cl.supporter.codes["PasswordInvalid"] = "I:011 | Invalid Password"
        self.cl.supporter.codes["GettingReady"] = "I:012 | Getting ready"
        self.cl.supporter.codes["ObsoleteClient"] = "I:013 | Client is out-of-date or unsupported"
        self.cl.supporter.codes["IDExists"] = "I:015 | Account exists"
        self.cl.supporter.codes["2FAOnly"] = "I:016 | 2FA Required"
        self.cl.supporter.codes["MissingPermissions"] = "I:017 | Missing permissions"
        self.cl.supporter.codes["Banned"] = "E:018 | Account Banned"
        self.cl.supporter.codes["IllegalChars"] = "E:019 | Illegal characters detected"
        self.cl.supporter.codes["Kicked"] = "E:020 | Kicked"
        self.cl.supporter.codes["ChatExists"] = "E:021 | Chat exists"
        self.cl.supporter.codes["ChatNotFound"] = "E:022 | Chat not found"
    
    
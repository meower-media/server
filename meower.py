from threading import Thread
from datetime import datetime
import time

class Meower:
    def __init__(self):
        # Load profanity filter
        self.log("Loading profanity filter...")
        file_read, payload = self.files.load_item("config", "filter")
        if file_read:
            self.supporter.profanity.load_censor_words(whitelist_words=payload["whitelist"])
            self.supporter.profanity.add_censor_words(custom_words=payload["blacklist"])
        else:
            self.log("Failed loading profanity filter.")

        # Get IP banned list
        self.log("Loading IP bans...")
        index = self.files.find_items("netlog", {"blocked": True})
        self.ip_banlist = index["index"]
        self.log("Loaded {0} IPs into IP banlist.".format(len(self.ip_banlist)))

        # Set repair status
        self.log("Loading server status...")
        file_read, payload = self.files.load_item("config", "status")
        if file_read:
            self.repair_mode = payload["repair_mode"]
            self.scratch_deprecated = payload["scratch_deprecated"]
            self.log("Loaded server status. Repair Mode: {0}, Scratch Deprecated: {1}".format(self.repair_mode, self.scratch_deprecated))
        else:
            self.log("Failed to load server status. Enabling repair mode to be safe.")
            self.repair_mode = True
            self.scratch_deprecated = False

        # Start WebSocket server
        self.log("Starting WebSocket server...")
        self.wss = Thread(target=self.ws.server, args=(self,)).start()

        # Start REST API
        self.log("Starting REST API...")
        self.rest_api_app = Thread(target=self.rest_api, args=(self,), kwargs={"ip": "0.0.0.0", "port": 3001}).start()

    def restart_services(self):
        self.log("Restarting services...")
        self.wss.stop()
        self.rest_api_app.stop()
        self.__init__()
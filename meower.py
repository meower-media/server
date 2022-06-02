from threading import Thread

class Meower:
    def __init__(self):
        # Load profanity filter
        FileRead, payload = self.files.load_item("config", "filter")
        if FileRead:
            self.supporter.profanity.load_censor_words(whitelist_words=payload["whitelist"])
            self.supporter.profanity.add_censor_words(custom_words=payload["blacklist"])

        # Set repair status
        FileRead, payload = self.files.load_item("config", "status")
        if FileRead:
            self.supporter.repair_mode = payload["repair_mode"]
            self.supporter.is_deprecated = payload["is_deprecated"]

        # Start WebSocket server
        self.wss = Thread(target=self.ws.server).start()

        # Start REST API
        self.rest_api_app = Thread(target=self.rest_api, args=(self,), kwargs={"ip": "0.0.0.0", "port": 3001}).start()

    def restart_services(self):
        self.wss.stop()
        self.rest_api_app.stop()
        self.__init__()
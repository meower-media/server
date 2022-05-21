from flask import request

class Endpoints:
    def __init__(self, app):
        self.app = app
        self.meower = self.app.meower
        self.respond = self.app.respond

        self.all_endpoints = [
            {
                "endpoint_name": "index",
                "endpoint_path": "/",
                "endpoint_function": self.index
            },
            {
                "endpoint_name": "status",
                "endpoint_path": "/status",
                "endpoint_function": self.get_status
            },
            {
                "endpoint_name": "ip_fetcher",
                "endpoint_path": "/ip",
                "endpoint_function": self.ip_fetcher
            },
            {
                "endpoint_name": "kick",
                "endpoint_path": "/kick/<user>",
                "endpoint_function": self.kick
            }
        ]
    
    def index(self):
        return self.respond({"test": "testing123"}, 200)

    def get_status(self):
        return self.respond({"isRepairMode": self.meower.supporter.repair_mode, "scratchDeprecated": self.meower.supporter.is_deprecated}, 200)
    
    def ip_fetcher(self):
        if "Cf-Connecting-Ip" in request.headers:
            return self.respond(str(request.headers["Cf-Connecting-Ip"]), 200)
        else:
            return self.respond(str(request.remote_addr), 200)

    def kick(self, user):
        return self.respond({"status": self.meower.cl.kickClient(user)}, 200)
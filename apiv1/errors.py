from flask import request

class Errors:
    def __init__(self, app):
        self.app = app
        self.respond = self.app.respond
        self.all_errors = [
            {
                "error_status": 404,
                "error_function": self.not_found
            },
            {
                "error_status": 405,
                "error_function": self.method_not_allowed
            },
            {
                "error_status": 500,
                "error_function": self.internal
            }
        ]
    
    def not_found(self, e):
        return self.respond({"type": "notFound"}, 404, error=True)
    
    def method_not_allowed(self, e):
        return self.respond({"type": "methodNotAllowed"}, 405, error=True)
    
    def internal(self, e):
        return self.respond({"type": "internal"}, 500, error=True)
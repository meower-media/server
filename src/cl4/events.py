from src.util import events
from src.cl4.cloudlink import cloudlink

class CL4Events:
    def __init__(self, cl_server: cloudlink):
        self.cl = cl_server

    @events.on("test")
    async def test(payload: dict):
        print("abc")
        print(payload)

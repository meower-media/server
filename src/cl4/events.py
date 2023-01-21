from src.util import events

class CL4Events:
    def __init__(self, cl_server):
        self.cl = cl_server

    @events.on("test")
    async def test(payload: dict):
        print(payload)

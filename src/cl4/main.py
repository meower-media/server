from cloudlink import cloudlink
from dotenv import load_dotenv

from src.cl4.events import CL4Events

# Load env variables
load_dotenv()

if __name__ == "__main__":
    cl = cloudlink()
    server = cl.server(logs=True)
    server._event_handler = CL4Events(server)
    server.run(ip="0.0.0.0", port=3000)

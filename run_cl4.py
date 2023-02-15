from dotenv import load_dotenv
import os

from src.cl4.server import cl
from src.util.startup import display_version

if __name__ == "__main__":
    load_dotenv()

    display_version()

    HOST = os.getenv("HOST", "127.0.0.1")
    CL4_PORT = os.getenv("CL4_PORT", 3001)

    cl.run(ip=HOST, port=CL4_PORT)

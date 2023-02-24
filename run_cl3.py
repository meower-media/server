from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

from src.cl3.server import cl
from src.util.startup import display_version

if __name__ == "__main__":
    display_version()

    HOST = os.getenv("HOST", "127.0.0.1")
    CL3_PORT = int(os.getenv("CL3_PORT", 3002))

    asyncio.run(cl.main(host=HOST, port=CL3_PORT))

from dotenv import load_dotenv
import os

from src.cdn.server import app
from src.util.startup import display_version

if __name__ == "__main__":
    load_dotenv()

    DEVELOPMENT = (os.getenv("DEVELOPMENT", "false") == "true")
    HOST = os.getenv("HOST", "127.0.0.1")
    CDN_PORT = int(os.getenv("CDN_PORT", 3002))

    display_version()

    try:
        app.run(host=HOST, port=CDN_PORT, debug=DEVELOPMENT, dev=DEVELOPMENT)
    except KeyboardInterrupt:
        exit()

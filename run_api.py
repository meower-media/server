from dotenv import load_dotenv
import os

load_dotenv()

from src.api.server import app
from src.util.startup import display_version

if __name__ == "__main__":
    DEVELOPMENT = (os.getenv("DEVELOPMENT", "false") == "true")
    HOST = os.getenv("HOST", "127.0.0.1")
    REST_PORT = int(os.getenv("REST_PORT", 3000))

    display_version()

    try:
        app.run(host=HOST, port=REST_PORT, debug=DEVELOPMENT, dev=DEVELOPMENT)
    except KeyboardInterrupt:
        exit()

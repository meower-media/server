from dotenv import load_dotenv
import os

from src.api.server import app
from src.util.startup import displayMeowerVersion

if __name__ == "__main__":
    load_dotenv()

    DEVELOPMENT = (os.getenv("DEVELOPMENT", "false") == "true")
    HOST = os.getenv("HOST", "127.0.0.1")
    REST_PORT = int(os.getenv("REST_PORT", 3000))

    displayMeowerVersion()

    try:
        app.run(host=HOST, port=REST_PORT, debug=DEVELOPMENT, dev=DEVELOPMENT)
    except KeyboardInterrupt:
        exit()

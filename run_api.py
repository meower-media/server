from dotenv import load_dotenv
import os

from src.api.server import app

if __name__ == "__main__":
    load_dotenv()

    DEVELOPMENT = (os.getenv("DEVELOPMENT", "false") == "true")

    try:
        app.run(host="0.0.0.0", port=8000, debug=DEVELOPMENT, dev=DEVELOPMENT)
    except KeyboardInterrupt:
        exit()

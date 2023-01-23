from dotenv import load_dotenv

from src.api.server import app

if __name__ == "__main__":
    load_dotenv()

    try:
        app.run(host="0.0.0.0", port=3000)
    except KeyboardInterrupt:
        exit()

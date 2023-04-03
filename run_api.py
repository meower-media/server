from src.api.server import app
from src.common.util import config, display_startup


if __name__ == "__main__":
    display_startup()

    try:
        app.run(host=config.host, port=config.api_port, debug=config.development)
    except KeyboardInterrupt:
        exit()

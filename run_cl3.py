import asyncio

from src.cl3.server import cl
from src.common.util import config, display_startup


if __name__ == "__main__":
	display_startup()

	asyncio.run(cl.main(host=config.host, port=config.cl3_port))

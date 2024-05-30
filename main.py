# Load .env file
from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import hypercorn

from threading import Thread

from cloudlink import CloudlinkServer
from supporter import Supporter
from commands import MeowerCommands
from security import background_tasks_loop
from grpc_auth import service as grpc_auth
from rest_api import app as rest_api


async def run():
    # Create Cloudlink server
    cl = CloudlinkServer()
    cl.set_real_ip_header(os.getenv("REAL_IP_HEADER"))
    cl.set_pseudo_trusted_access(True)
    cl.set_motd("Meower Social Media Platform Server")
    cl.remove_command("setid")
    cl.remove_command("gmsg")
    cl.remove_command("gvar")

    # Create Supporter class
    supporter = Supporter(cl)

    # Initialise Meower commands
    MeowerCommands(cl, supporter)

    # Start background tasks loop
    Thread(target=background_tasks_loop, daemon=True).start()

    # Start gRPC services
    Thread(target=grpc_auth.serve, daemon=True).start()

    # Initialise REST API
    rest_api.cl = cl
    rest_api.supporter = supporter

    # Start REST API
    hypercorn_conf = hypercorn.config.Config()
    hypercorn_conf.bind = os.getenv("API_HOST", "0.0.0.0")+":"+os.getenv("API_PORT", "3001")
    asyncio.create_task(hypercorn.asyncio.serve(rest_api, hypercorn_conf))

    # Start Cloudlink server
    asyncio.create_task(cl.run(
        host=os.getenv("CL3_HOST", "0.0.0.0"),
        port=int(os.getenv("CL3_PORT", 3000))
    ))

    # Run forever
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run())

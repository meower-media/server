from cloudlink import cloudlink
from dotenv import load_dotenv

from src.util import events

# Load env variables
load_dotenv()

@events.on("test")
async def test(payload: dict):
    print("abc")
    print(payload)

if __name__ == "__main__":
    cl = cloudlink().server(logs=True)
    cl.run(ip="0.0.0.0", port=3000)

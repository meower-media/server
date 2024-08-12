import requests
import json

import websockets.sync.client
from websockets.sync.client import connect
import pymongo
import dotenv

config = dotenv.dotenv_values(".env")  # Main environment variables that the server uses

if config["CAPTCHA_SITEKEY"] != "":
	print("Please disable captchas in your .env file before running this script.")
	exit(1)


db = pymongo.MongoClient(config["MONGO_URI"])[config["MONGO_DB"]]


USERNAME = "test"
PRONOUNS = [
	["he", "him"],
	["they", "them"]
]

API = config["INTERNAL_API_ENDPOINT"]

db.get_collection("usersv0").delete_one({"_id": USERNAME})
db.get_collection("user_settings").delete_one({"_id": USERNAME})

resp = requests.post(API + "/auth/register", json={
	"username": USERNAME,
	"password": "password",
}).json()

websocket = connect(f"ws://localhost:{config["CL3_PORT"]}/?v=1&token={resp["token"]}")

USER = json.loads(websocket.recv())["val"]

TOKEN = USER["token"]

if USER["account"]["pronouns"]:
	print("Pronouns already set.")
	exit(1)


requests.patch(API + "/me/config", json={
	"pronouns": PRONOUNS
}, headers={
	"token": TOKEN

})

websocket.recv()
websocket.recv()
websocket.recv()



requests.post(API + "/home/", json={
	"content": "content"
}, headers={
	"token": TOKEN
})
p = websocket.recv()
post = json.loads(p)["val"]

if post["author"]["pronouns"] != PRONOUNS:
	print("Pronouns not set.")
	websocket.close()
	exit(1)

websocket.close()

print("Pronouns test passed.")

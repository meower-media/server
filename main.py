# Initialize API
from flask import Flask, request
meower = Flask(__name__)

# Initialize Utils
from apiv0.utils import log, timestamp, check_for_bad_chars_post, check_for_bad_chars_username
meower.log = log
meower.timestamp = timestamp
meower.check_for_bad_chars_post = check_for_bad_chars_post
meower.check_for_bad_chars_username = check_for_bad_chars_username

# Initialize Responder
from apiv0.respond import respond
meower.respond = respond

# Initialize database
import pymongo
meower.db = pymongo.MongoClient("mongodb://localhost:27017")["meowerserver"]

# Register blueprints
from apiv0.errors import errors
meower.register_blueprint(errors)
from apiv0.general import general
meower.register_blueprint(general, name="compatibility_general") # Keep general endpoints as root for compatibility
meower.register_blueprint(general, url_prefix="/v0")
from apiv0.admin import admin
meower.register_blueprint(admin, url_prefix="/v0/admin")
from apiv0.oauth import oauth
meower.register_blueprint(oauth, url_prefix="/v0/oauth")
from apiv0.users import users
meower.register_blueprint(users, url_prefix="/v0/users")
from apiv0.home import home
meower.register_blueprint(home, url_prefix="/v0/home")
from apiv0.chats import chats
meower.register_blueprint(chats, url_prefix="/v0/chats")
from apiv0.search import search
meower.register_blueprint(search, url_prefix="/v0/search")

# Initialize Socket
from flask_sock import Sock
from apiv0.socket import Socket
sock = Sock(meower)
meower.sock_clients = {
    "users": {},
    "sessions": {},
    "ips": {}
}
@sock.route("/v0/socket")
def socket_server(client):
    return Socket(meower, client)

# Initialize CORS
from flask_cors import CORS
CORS(meower, resources={r'*': {'origins': '*'}})

# Set repair mode and scratch deprecated state
data = meower.db["config"].find_one({"_id": "status"})
if data is None:
    meower.log("Failed getting server status. Enabling repair mode to be safe.")
    meower.repair_mode = True
    meower.scratch_deprecated = False
else:
    meower.repair_mode = data["repair_mode"]
    meower.scratch_deprecated = data["scratch_deprecated"]

# Set email authentication key
data = meower.db["config"].find_one({"_id": "email_auth_key"})
if data is None:
    meower.log("Failed getting email authentication key. Emails will not be sent.")
    meower.email_auth_key = None
else:
    meower.email_auth_key = data["key"]

# Run Flask app
meower.run(host="0.0.0.0", port=3000, debug=True)
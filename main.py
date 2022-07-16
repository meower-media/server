# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize API
from flask import Flask, request
meower = Flask(__name__)

# Initialize Utils
from apiv0.utils import Utils, Session, User
utils = Utils(meower, request)
meower.sock_statuses = utils.sock_statuses
meower.log = utils.log
meower.timestamp = utils.timestamp
meower.create_session = utils.create_session
meower.foundation_session = utils.foundation_session
meower.check_for_spam = utils.check_for_spam
meower.check_for_bad_chars_post = utils.check_for_bad_chars_post
meower.check_for_bad_chars_username = utils.check_for_bad_chars_username
meower.filter = utils.filter
meower.user_status = utils.user_status
meower.send_payload = utils.send_payload
meower.encrypt = utils.encrypt
meower.decrypt = utils.decrypt
meower.is_valid_email = utils.is_valid_email
meower.send_email = utils.send_email
meower.init_db = utils.init_db
meower.check_for_json = utils.check_for_json
meower.check_for_params = utils.check_for_params
meower.require_auth = utils.require_auth
meower.Session = Session
meower.User = User

# Initialize encryption
utils.init_encryption()

# Initialize Responder
from apiv0.respond import respond
meower.respond = respond

# Initialize database
import pymongo
meower.log("Connecting to MongoDB... (if it looks like the server is stuck or randomly crashes, it probably couldn't connect to the database)")
meower.db = pymongo.MongoClient("mongodb://localhost:27017").meowerserver
meower.init_db()

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
from apiv0.settings import settings
meower.register_blueprint(settings, url_prefix="/v0/settings")
from apiv0.users import users
meower.register_blueprint(users, url_prefix="/v0/users")
from apiv0.home import home
meower.register_blueprint(home, url_prefix="/v0/home")
from apiv0.chats import chats
meower.register_blueprint(chats, url_prefix="/v0/chats")
from apiv0.search import search
meower.register_blueprint(search, url_prefix="/v0/search")

# Initialize WebSocket
from flask_sock import Sock
from apiv0.socket import SocketClient
flask_sock = Sock(meower)
meower.sock_clients = {}
@flask_sock.route("/v0/socket")
def socket_server(client):
	SocketClient(meower, client)

# Initialize CORS
from flask_cors import CORS
CORS(meower, resources={r'*': {'origins': '*'}})

# Load profanity filter
from better_profanity import profanity
meower.profanity = profanity
meower.log("Loading profanity filter...")
filter = meower.db["config"].find_one({"_id": "filter"})
meower.profanity.load_censor_words(whitelist_words=filter["whitelist"])
meower.profanity.add_censor_words(custom_words=filter["blacklist"])
meower.blocked_usernames = filter["blocked_usernames"]

# Load IP bans into memory
meower.log("Loading IP bans...")
meower.ip_banlist = []
ip_bans = meower.db.netlog.find({"blocked": True})
for ip in ip_bans:
	meower.ip_banlist.append(ip["_id"])

# Set repair mode and scratch deprecated state
status = meower.db["config"].find_one({"_id": "status"})
for key, value in status.items():
	if key != "_id":
		setattr(meower, key, value)

# Run Flask app
meower.run(host="0.0.0.0", port=3000, debug=True)
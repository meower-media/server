from datetime import datetime
import time
import string
import requests
from threading import Thread
import os
import shutil
import json
import serial
from cryptography.fernet import Fernet
from uuid import uuid4
import secrets
from better_profanity import profanity
import pymongo
from jinja2 import Template
import copy
import geocoder

class Utils:
    def __init__(self, meower, request):
        self.meower = meower
        self.request = request

        # Ratelimits
        meower.last_packet = {}
        meower.burst_amount = {}
        meower.ratelimits = {}

        # Permitted lists of characters for posts
        self.permitted_chars_post = []
        self.permitted_chars_post.extend(string.ascii_letters)
        self.permitted_chars_post.extend(string.digits)
        self.permitted_chars_post.extend(string.punctuation)
        self.permitted_chars_post.append(" ")

        # Permitted lists of characters for usernames
        self.permitted_chars_username = self.permitted_chars_post.copy()
        for item in [
            '"',
            "'",
            "*",
            ";"
        ]:
            self.permitted_chars_username.remove(item)

        # WebSocket status codes
        self.sock_statuses = {
            "OK": "I:100 | OK",
            "Syntax": "E:101 | Syntax",
            "Datatype": "E:102 | Datatype",
            "TooLarge": "E:103 | Packet too large",
            "Internal": "E:104 | Internal",
            "InvalidToken": "E:106 | Invalid token",
        }

        # OAuth scopes
        self.all_oauth_scopes = set([
            "foundation:profile:view_profile",
            "foundation:settings:read_email",
            "foundation:settings:read_config",
            "foundation:settings:edit_config",
            "foundation:inbox:read_messages",
            "meower:websocket:connect",
            "meower:chats:access",
            "meower:chats:edit",
            "meower:posts:read_posts",
            "meower:posts:create_posts",
            "meower:posts:edit_posts",
            "meower:posts:comments"
        ])
        self.first_party_oauth_scopes = set([
            "foundation:settings:authentication",
            "foundation:settings:sessions",
            "foundation:settings:blocked",
            "foundation:settings:danger",
            "foundation:oauth:authorized",
            "foundation:oauth:apps"
        ])

        # Start background task
        background_thread = Thread(target=self.background)
        background_thread.daemon = True
        background_thread.start()

    def background(self):
        while True:
            # Background task runs every 60 seconds
            time.sleep(60)

            # Purge any expired sessions
            self.meower.db["sessions"].delete_many({"type": {"$in": [0,1,3,4,6]}, "expires": {"$lt": time.time()}})
            self.meower.db["sessions"].delete_many({"refresh_expires": {"$lt": time.time()}})

            # Purge accounts pending deletion
            users = self.meower.db["usersv0"].find({"security.delete_after": {"$lt": time.time()}})
            for user in users:
                # Delete posts
                self.meower.db["posts"].delete_many({"u": user["_id"]})

                # Delete sessions
                self.meower.db["sessions"].delete_many({"user": user["_id"]})

                # Delete OAuth apps
                oauth_apps = self.meower.db["oauth"].find({"owner": user["_id"]})
                for app in oauth_apps:
                    oauth_users = self.meower.db["usersv0"].find({"security.oauth.authorized": {"$all": [app["_id"]]}})
                    for oauth_user in oauth_users:
                        oauth_user["security"]["oauth"]["authorized"].remove(app["_id"])
                        del oauth_user["security"]["oauth"]["scopes"][app["_id"]]
                        self.meower.db["usersv0"].update_one({"_id": oauth_user["_id"]}, {"$set": {"security.oauth": oauth_user["security"]["oauth"]}})
                    self.meower.db["oauth"].delete_one({"_id": app["_id"]})

                # Delete chats
                chats = self.meower.db["chats"].find({"members": {"$all": [user["_id"]]}})
                for chat in chats:
                    if chat["permissions"][user["_id"]] >= 3:
                        self.meower.db["chats"].delete_one({"_id": chat["_id"]})
                    else:
                        chat["members"].remove(user["_id"])
                        del chat["permissions"][user["_id"]]
                        self.meower.db["chats"].update_one({"_id": chat["_id"]}, {"$set": {"members": chat["members"]}})

                # Schedule bots for deletion
                self.meower.db["usersv0"].update_many({"owner": user["_id"]}, {"$set": {"security.delete_after": time.time()}})

                # Delete userdata
                self.meower.db["usersv0"].delete_one({"_id": user["_id"]})

    def log(self, msg, prefix=None):
        if prefix is None:
            print("{0}: {1}".format(self.timestamp(4), msg))
        else:
            print("[{0}] {1}: {2}".format(prefix, self.timestamp(4), msg))

    def timestamp(self, ttype, epoch=int(time.time())):
        today = datetime.fromtimestamp(epoch)
        if ttype == 1:
            return dict({
                "mo": str(datetime.now().strftime("%m")),
                "d": str(datetime.now().strftime("%d")),
                "y": str(datetime.now().strftime("%Y")),
                "h": str(datetime.now().strftime("%H")),
                "mi": str(datetime.now().strftime("%M")),
                "s": str(datetime.now().strftime("%S")),
                "e": int(time.time())
            })
        elif ttype == 2:
            return str(today.strftime("%H%M%S"))
        elif ttype == 3:
            return str(today.strftime("%d%m%Y%H%M%S"))
        elif ttype == 4:
            return str(today.strftime("%m/%d/%Y %H:%M.%S"))
        elif ttype == 5:    
            return str(today.strftime("%d%m%Y"))

    def create_session(self, type, user, token, email=None, expires=None, action=None, app=None, scopes=None):
        # Base session data
        session_data = {
            "_id": str(uuid4()),
            "type": type,
            "user": user,
            "user_agent": None,
            "token": token,
            "expires": None,
            "created": time.time()
        }
        
        # Add user agent
        try:
            session_data["user_agent"] = self.request.headers["User-Agent"]
        except:
            pass

        # Add specific data for each type
        if type == 0:
            session_data["action"] = action
            session_data["email"] = email
        elif type == 1:
            session_data["verified"] = False
        elif type == 4:
            session_data["app"] = app
            session_data["scopes"] = scopes
        elif type == 5:
            session_data["app"] = app
            session_data["scopes"] = scopes
            session_data["refresh_token"] = str(secrets.token_urlsafe(128))
            session_data["refresh_expires"] = time.time() + 31556952
            session_data["previous_refresh_tokens"] = []

        # Add any missing data
        for item in ["email", "action", "verified", "app", "scopes", "refresh_token", "refresh_expires", "previous_refresh_tokens"]:
            if item not in session_data:
                session_data[item] = None

        # Set expiration time
        if expires is not None:
            session_data["expires"] = time.time() + expires
        else:
            session_data["expires"] = time.time() + {1: 300, 2: 300, 3: 31556952, 4: 1800}[session_data["type"]]

        # Add session to database and return session data
        self.meower.db["sessions"].insert_one(session_data)
        return session_data

    def foundation_session(self, user):
        # Create session
        session = self.create_session(3, user, secrets.token_urlsafe(64))
        session["previous_refresh_tokens"] = None

        # Get user data and check if it's pending deletion
        userdata = self.meower.db["usersv0"].find_one({"_id": user})
        if userdata["security"]["delete_after"] is not None:
            self.meower.db["usersv0"].update_one({"_id": userdata["_id"]}, {"$set": {"security.delete_after": None}})

        # Alert user of new login
        if userdata["security"]["email"] is None:
            email = None
        else:
            email = self.meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
        if email is not None:
            ip_details = geocoder.ip(self.request.remote_addr)
            with open("apiv0/email_templates/alerts/new_login.html", "r") as f:
                email_template = Template(f.read()).render({"username": userdata["username"], "ip": self.request.remote_addr, "city": ip_details.city, "country": ip_details.country})
            Thread(target=self.meower.send_email, args=(email, userdata["username"], "Security Alert", email_template,), kwargs={"type": "text/html"}).start()

        # Delete security before returning to user
        del userdata["security"]

        # Return session data
        return {"session": session, "user": userdata, "requires_totp": False}

    def check_for_spam(self, type, client, burst=1, seconds=1):
        # Check if type and client are in ratelimit dictionary
        if not (type in self.meower.last_packet):
            self.meower.last_packet[type] = {}
            self.meower.burst_amount[type] = {}
            self.meower.ratelimits[type] = {}
        if client not in self.meower.last_packet[type]:
            self.meower.last_packet[type][client] = 0
            self.meower.burst_amount[type][client] = 0
            self.meower.ratelimits[type][client] = 0

        # Check if user is currently ratelimited
        if self.meower.ratelimits[type][client] > time.time():
            return True

        # Check if max burst has expired
        if (self.meower.last_packet[type][client] + seconds) < time.time():
            self.meower.burst_amount[type][client] = 0

        # Set last packet time and add to burst amount
        self.meower.last_packet[type][client] = time.time()
        self.meower.burst_amount[type][client] += 1

        # Check if burst amount is over max burst
        if self.meower.burst_amount[type][client] > burst:
            self.meower.ratelimits[type][client] = (time.time() + seconds)
            self.meower.burst_amount[type][client] = 0
            return True
        else:
            return False

    def check_for_bad_chars_username(self, message):
        for char in message:
            if not char in self.permitted_chars_username:
                return True
        return False

    def check_for_bad_chars_post(self, message):
        for char in message:
            if not char in self.permitted_chars_post:
                return True
        return False

    def check_for_auto_suspension(self, user):
        # Check how many posts have been auto censored
        total_auto_censored = 4
        deleted_posts = self.meower.db["posts"].find({"u": user, "isDeleted": True})
        for post in deleted_posts:
            report_status = self.meower.db["reports"].find_one({"_id": post["_id"]})
            if report_status["auto_suspended"] and (report_status["review_status"] == 0):
                total_auto_censored += 1
                if total_auto_censored > 3:
                    break
        
        # Suspend user if they have more than 3 auto-censored posts that are not reviewed
        if total_auto_censored > 3:
            # Set suspension time
            self.meower.db["usersv0"].update_one({"_id": user}, {"$set": {"security.suspended_until": time.time() + 43200}})

            # Render and send alert email
            userdata = self.meower.db["usersv0"].find_one({"_id": user})
            if userdata["security"]["email"] is None:
                email = None
            else:
                email = self.meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
            if email is not None:
                with open("apiv0/email_templates/moderation/suspension.html", "r") as f:
                    email_template = Template(f.read()).render({"username": userdata["username"], "reason": "Automatic suspension due to too many posts flagged for moderation.", "expires": "In 12 hours or when the flagged posts are reviewed"})
                Thread(target=self.meower.send_email, args=(email, userdata["username"], "Notice of temporary account suspension", email_template,), kwargs={"type": "text/html"}).start()

    def filter(self, message):
        message = self.meower.filter.censor(message)
        for word in self.meower.filter.CENSOR_WORDSET:
            message = message.replace(str(word), ("*" * len(word)))
        return message

    def user_status(self, user):
        userdata = self.meower.db["usersv0"].find_one({"_id": user})
        if userdata is None:
            return "Offline"

        status = userdata["profile"]["status"]
        if userdata["security"]["banned"]:
            return "Banned"
        elif (userdata["security"]["suspended_until"] is not None) and (userdata["security"]["suspended_until"] > time.time()):
            return "Suspended"
        else:
            if user in self.meower.sock_clients:
                if (status < 0) or (status > 3):
                    return "Online"
                else:
                    return ["Offline", "Online", "Away", "Do Not Disturb"][status]
            else:
                return "Offline"

    def export_data(self, user):
        # Create export ID
        export_id = str(uuid4())

        # Create directory to store exported data
        os.mkdir("apiv0/data_exports/{0}".format(export_id))
        os.mkdir("apiv0/data_exports/{0}/sessions".format(export_id))
        os.mkdir("apiv0/data_exports/{0}/posts".format(export_id))
        os.mkdir("apiv0/data_exports/{0}/chats".format(export_id))
        os.mkdir("apiv0/data_exports/{0}/oauth_apps".format(export_id))
        os.mkdir("apiv0/data_exports/{0}/bots".format(export_id))

        # Create user.json
        userdata = self.meower.db["usersv0"].find_one({"_id": user})
        if userdata is not None:
            exported_userdata = copy.deepcopy(userdata)
            for item in ["email", "password", "webauthn", "totp", "moderation_history"]:
                exported_userdata["security"][item] = None
            with open("apiv0/data_exports/{0}/user.json".format(export_id), "w") as f:
                json.dump(exported_userdata, f, indent=4)

        # Get all sessions
        sessions = self.meower.db["sessions"].find({"user": user})
        for session in sessions:
            session["token"] = None
            session["email"] = None
            session["refresh_token"] = None
            session["previous_refresh_tokens"] = None
            with open("apiv0/data_exports/{0}/sessions/{1}.json".format(export_id, session["_id"]), "w") as f:
                json.dump(session, f, indent=4)

        # Get all posts
        index = {"order_key": "t", "order_mode": "Descending"}
        posts = self.meower.db["posts"].find({"u": user}).sort("t", pymongo.DESCENDING)
        for post in posts:
            if post["post_origin"] not in os.listdir("apiv0/data_exports/{0}/posts".format(export_id)):
                os.mkdir("apiv0/data_exports/{0}/posts/{1}".format(export_id, post["post_origin"]))
                index[post["post_origin"]] = []
            with open("apiv0/data_exports/{0}/posts/{1}/{2}.json".format(export_id, post["post_origin"], post["_id"]), "w") as f:
                json.dump(post, f, indent=4)
            index[post["post_origin"]].append(post["_id"])
        with open("apiv0/data_exports/{0}/chats/index.json".format(export_id), "w") as f:
            json.dump(index, f, indent=4)

        # Get all chats
        chats = self.meower.db["chats"].find({"members": {"$all": [user]}, "deleted": False}).sort("nickname", pymongo.DESCENDING)
        for chat in chats:
            with open("apiv0/data_exports/{0}/chats/{1}.json".format(export_id, chat["_id"]), "w") as f:
                json.dump(chat, f, indent=4)

        # Get OAuth apps
        oauth_apps = self.meower.db["oauth"].find({"owner": user})
        for app in oauth_apps:
            app["secret"] = None
            with open("apiv0/data_exports/{0}/oauth_apps/{1}.json".format(export_id, app["_id"]), "w") as f:
                json.dump(app, f, indent=4)

        # Create ZIP file
        if "{0}.zip".format(user) in os.listdir("apiv0/data_exports"):
            os.remove("apiv0/data_exports/{0}.zip".format(user))
        shutil.make_archive("apiv0/data_exports/{0}".format(user), "zip", "apiv0/data_exports/{0}".format(export_id))

        # Delete export directory
        shutil.rmtree("apiv0/data_exports/{0}".format(export_id))

        # Create session for downloading the package
        session = self.meower.create_session(0, user, str(secrets.token_urlsafe(32)), expires=86400, action="download-data")

        # Send email
        if userdata["security"]["email"] is None:
            email = None
        else:
            email = self.meower.decrypt(userdata["security"]["email"]["encryption_id"], userdata["security"]["email"]["encrypted_email"])
        if email is not None:
            with open("apiv0/email_templates/confirmations/download_data.html", "r") as f:
                email_template = Template(f.read()).render({"username": userdata["username"], "token": session["token"]})
            Thread(target=self.meower.send_email, args=(email, userdata["username"], "Your data package is ready", email_template,), kwargs={"type": "text/html"}).start()

    def send_payload(self, payload, user=None):
        if user.raw is None:
            for user, clients in self.meower.sock_clients.items():
                for sock_client in clients:
                    sock_client.client.send(payload)
        else:
            if user in self.meower.sock_clients:
                for sock_client in self.meower.sock_clients[user]:
                    sock_client.client.send(payload)

    def init_encryption(self):
        self.meower.meowkey = None
        self.meower.encryption = None
        try:
            if os.environ["ENCRYPTION_KEY_FROM"] == "env":
                key = os.environ["ENCRYPTION_KEY"]
            elif os.environ["ENCRYPTION_KEY_FROM"] == "meowkey":
                self.meower.meowkey = EasyUART(os.environ["MEOWKEY_PORT"])
                self.meower.meowkey.connect()
                self.meower.meowkey.rx()
                self.meower.meowkey.tx(json.dumps({"cmd": "ACK?"}))
                signal = json.loads(self.meower.meowkey.rx())
                if signal["cmd"] == "ACK!":
                    self.meower.meowkey.tx(json.dumps({"cmd": "KEY?"}))
                    key = json.loads(self.meower.meowkey.rx())
                    if key["cmd"] == "KEY!":
                        key = key["key"]
                    else:
                        key = None
                        self.log("MeowKey refused to send encryption key")
            if key is not None:
                self.meower.encryption = Fernet(key.encode())
        except:
            pass
        if "encryption_keys" not in os.listdir():
            os.mkdir("encryption_keys")
        if self.meower.encryption is None:
            self.log("Failed to initialize encryption -- Emails will not work")

    def destroy_key_on_meowkey_disconnect(self):
        while not self.meower.meowkey.bus.connected:
            self.meower.meowkey = None
            self.meower.encryption = None
            self.meower.log("Disconnected from MeowKey -- Emails will no longer work")

    def encrypt(self, data):
        new_key = Fernet.generate_key()
        encrypted_data = Fernet(new_key).encrypt(data.encode()).decode()
        new_uuid = str(uuid4())
        with open("encryption_keys/{0}".format(new_uuid), "w") as f:
            f.write(self.meower.encryption.encrypt(new_key).decode())
        return new_uuid, encrypted_data

    def decrypt(self, id, data):
        with open("encryption_keys/{0}".format(id), "r") as f:
            encryption_key = self.meower.encryption.decrypt(f.read().encode()).decode()
        decrypted_data = Fernet(encryption_key).decrypt(data.encode()).decode()
        return decrypted_data

    def is_valid_email(self, email):
        # Check if the email contains an @
        if "@" not in email:
            return False
        
        # Check if the email address domain is valid
        email = email.split("@")
        if email[1].count(".") != 1:
            return False
        else:
            return True

    def send_email(self, email, username, subject, body, type="text/plain"):
        payload = {
            "personalizations": [{
                "to": [{
                    "email": email,
                    "name": username
                }],
                "dkim_domain": os.getenv("EMAIL_DOMAIN"),
                "dkim_selector": "mailchannels",
                "dkim_private_key": os.getenv("EMAIL_DKIM_KEY")
            }],
            "from": {
                "email": "no-reply@{0}".format(os.getenv("EMAIL_DOMAIN")),
                "name": "Meower"
            },
            "subject": subject,
            "content": [{
                "type": type,
                "value": body
            }]
        }

        return requests.post(os.getenv("EMAIL_WORKER_URL"), headers={"X-Auth-Token": os.getenv("EMAIL_WORKER_TOKEN")}, json=payload)

    def init_db(self):
        with open("db_template.json", "r") as f:
            db_data = json.loads(f.read())
        for collection_name, collection_data in db_data.items():
            for index_name in collection_data["indexes"]:
                try:
                    self.meower.db[collection_name].create_index(index_name)
                except:
                    pass
            for item in collection_data["items"]:
                try:
                    self.meower.db[collection_name].insert_one(item)
                except:
                    pass

    def check_for_json(self, data=[]):
        """
        id: JSON key
        t: expected datatype
        l_min: length minimum
        l_max: length maximum
        r_min: range minimum
        r_max: range maximum
        """

        for item in data:
            if item["id"] not in self.request.json:
                return self.meower.respond({"type": "missingField", "message": "Missing required JSON data: {0}".format(item["id"])}, 400, error=True)
            elif ("t" in item) and (type(self.request.json[item["id"]]) is not item["t"]):
                return self.meower.respond({"type": "datatype", "message": "Invalid datatype for JSON data: {0}".format(item["id"])}, 400, error=True)
            elif ("l_min" in item) and (len(str(self.request.json[item["id"]])) < item["l_min"]):
                return self.meower.respond({"type": "invalidLength", "message": "Invalid length for JSON data: {0}".format(item["id"])}, 400, error=True)
            elif ("l_max" in item) and (len(str(self.request.json[item["id"]])) > item["l_max"]):
                return self.meower.respond({"type": "invalidLength", "message": "Invalid length for JSON data: {0}".format(item["id"])}, 400, error=True)
            elif (("r_min") in item) and (self.request.json[item["id"]] < item["r_min"]):
                return self.meower.respond({"type": "outOfRange", "message": "Out of range value for JSON data: {0}".format(item["id"])}, 400, error=True)
            elif (("r_max") in item) and (self.request.json[item["id"]] > item["r_max"]):
                return self.meower.respond({"type": "outOfRange", "message": "Out of range value for JSON data: {0}".format(item["id"])}, 400, error=True)

    def check_for_params(self, data=[]):
        for item in data:
            if item not in self.request.args:
                return self.meower.respond({"type": "missingParam", "message": "Missing required param: {0}".format(item)}, 400, error=True)
    
    def require_auth(self, allowed_types, levels=[-1, 0, 1, 2, 3], scope=None, check_suspension=False):
        if self.request.method != "OPTIONS":
            # Check if session is valid
            if not self.request.session.authed:
                return self.meower.respond({"type": "unauthorized", "message": "You are not authenticated."}, 401, error=True)
            
            # Check session type
            if self.request.session.type not in allowed_types:
                return self.meower.respond({"type": "forbidden", "message": "You are not allowed to perform this action."}, 403, error=True)
            
            # Check session scopes
            if (self.request.session.type == 5) and (scope is not None) and (scope not in self.request.session.scopes):
                return self.meower.respond({"type": "forbidden", "message": "You are not allowed to perform this action."}, 403, error=True)

            # Check if session is verified (only for certain types)
            if (self.request.session.verified != None) and (self.request.session.verified != True):
                return self.meower.respond({"type": "unauthorized", "message": "Session has not been verified yet."}, 401, error=True)

            # Check user
            userdata = self.meower.db["usersv0"].find_one({"_id": self.request.user._id})
            if (userdata is None) or userdata["security"]["banned"]:
                self.request.session.delete()
                return self.meower.respond({"type": "unauthorized", "message": "You are not authenticated."}, 401, error=True)
            elif userdata["state"] not in levels:
                return self.meower.respond({"type": "forbidden", "message": "You are not allowed to perform this action."}, 403, error=True)
            elif check_suspension and (userdata["security"]["suspended_until"] is not None) and (userdata["security"]["suspended_until"] > time.time()):
                return self.meower.respond({"type": "forbidden", "message": "You are suspended from performing this action."}, 403, error=True)

class Session:
    def __init__(self, meower, token):
        self.meower = meower

        # Get session data from database
        token_data = self.meower.db.sessions.find_one({"token": token})
        
        # Check if session is valid
        self.authed = False
        try:
            if (token_data is not None) and (token_data["type"] == 3 or token_data["type"] == 5):
                self.json = token_data
                for key, value in token_data.items():
                    setattr(self, key, value)
                self.user = self.meower.User(self.meower, user_id=self.user)
                if (self.expires == None) or (not (self.expires < time.time())) and (self.user.raw is not None):
                    self.authed = True
        except:
            pass

    def renew(self):
        # Renew session
        self.meower.db.sessions.update_one({"_id": self._id}, {"$set": {"expires": time.time() + self.expires}})
        self.expires = time.time() + self.expires
    
    def delete(self):
        # Delete session
        self.meower.db.sessions.delete_one({"_id": self._id})

class User:
    def __init__(self, meower, user_id=None, username=None):
        if user_id is not None:
            self.raw = meower.db["usersv0"].find_one({"_id": user_id})
        elif username is not None:
            self.raw = meower.db["usersv0"].find_one({"lower_username": username.lower()})
        else:
            self.raw = None

        if self.raw is None:
            return
        
        for key, value in self.raw.items():
            setattr(self, key, value)

        self.profile = {
            "_id": self._id,
            "username": self.username,
            "lower_username": self.lower_username,
            "pfp": self.profile["pfp"],
            "quote": self.profile["quote"],
            "status": meower.user_status(self._id),
            "created": self.created
        }

        self.client = self.raw.copy()
        del self.client["security"]

class EasyUART:
    def __init__(self, port):
        self.bus = serial.Serial(port = port, baudrate = 9600)
        
    def connect(self): # This code is platform specific
        if not self.bus.connected:
            while not self.bus.connected:
                time.sleep(1)
        self.bus.reset_input_buffer()
        return True
    
    def tx(self, payload): # Leave encoding as ASCII since literally everything supports it
        self.bus.write(bytes(payload + "\r", "ASCII"))
    
    def rx(self):
        done = False
        tmp = ""
        while not done:
            # Listen for new data
            if self.bus.in_waiting != 0:
                readin = self.bus.read(self.bus.in_waiting).decode("ASCII")
                
                for thing in readin:
                    if thing == "\r":
                        done = True
                    else:
                        tmp += thing
        return tmp
from __main__ import meower
from datetime import datetime
import time
import string
import requests
from threading import Thread
import os
import json

# Create ratelimits
meower.ratelimits = {}

# Create permitted lists of characters for posts
permitted_chars_post = []
permitted_chars_post.extend(string.ascii_letters)
permitted_chars_post.extend(string.digits)
permitted_chars_post.extend(string.punctuation)
permitted_chars_post.append(" ")

# Create permitted lists of characters for usernames
permitted_chars_username = permitted_chars_post.copy()
for item in [
    '"',
    "'",
    "*",
    ";"
]:
    permitted_chars_username.remove(item)

def log(msg, prefix=None):
    if prefix is None:
        print("{0}: {1}".format(timestamp(4), msg))
    else:
        print("[{0}] {1}: {2}".format(prefix, timestamp(4), msg))

def timestamp(ttype, epoch=int(time.time())):
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

def check_for_spam(type: str, client: str, seconds: float=1):
    if not (type in meower.ratelimits):
        meower.ratelimits[type] = {}

    if not (client in meower.ratelimits[type]):
        meower.ratelimits[type][client] = 0
    
    if meower.ratelimits[type][client] > time.time():
        return True
    else:
        meower.ratelimits[type][client] = time.time() + seconds
        return False

def check_for_bad_chars_username(message):
    for char in message:
        if not char in permitted_chars_username:
            return True
    return False

def check_for_bad_chars_post(message):
    for char in message:
        if not char in permitted_chars_post:
            return True
    return False

def user_status(user):
    userdata = meower.db["usersv0"].find_one({"_id": user})
    if userdata is None:
        return "Offline"
    else:
        status = userdata["profile"]["status"]
        if userdata["security"]["banned_until"] > int(time.time()):
            return "Temporarily Banned"
        elif userdata["security"]["banned_until"] == -1:
            return "Permanently Banned"
        else:
            if user in meower.sock_clients:
                return ["Offline", "Online", "Away", "Do Not Disturb"][status]
            else:
                return "Offline"

def send_payload(payload, user=None):
    if user is None:
        for user, clients in meower.sock_clients.items():
            for sock_client in clients:
                sock_client.client.send(payload)
    else:
        if user in meower.sock_clients:
            for sock_client in meower.sock_clients[user]:
                sock_client.client.send(payload)

def send_email(users, subject, body, type="text/plain", unverified_emails=False):
    def run(payload):
        return requests.post(os.getenv("EMAIL_WORKER_URL"), headers={"X-Auth-Token": os.getenv("EMAIL_WORKER_TOKEN")}, json=payload)

    template = {
        "personalizations": [{
            "to": [],
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
    
    for user in users:
        userdata = meower.db["usersv0"].find_one({"_id": user})
        if userdata is not None:
            payload = template.copy()
            for method in userdata["security"]["authentication_methods"]:
                if method["type"] != "email":
                    continue
                elif not (unverified_emails or method["verified"]):
                    continue
                else:
                    payload["personalizations"][0]["to"].append({
                        "email": method["encrypted_email"],
                        "name": userdata["username"]
                    })
            Thread(target=run, args=(payload,)).start()

def init_db():
    with open("db_template.json", "r") as f:
        db_data = json.loads(f.read())
    for collection_name, collection_data in db_data.items():
        for index_name in collection_data["indexes"]:
            try:
                meower.db[collection_name].create_index(index_name)
            except:
                pass
        for item in collection_data["items"]:
            try:
                meower.db[collection_name].insert_one(item)
            except:
                pass

class Session:
    def __init__(self, token):
        # Get session data from database
        token_data = meower.db.sessions.find_one({"token": token})
        
        # Check if session is valid
        self.authed = False
        try:
            if (token_data is not None) and (token_data["type"] == 3 or token_data["type"] == 5):
                self.json = token_data
                for key, value in token_data.items():
                    setattr(self, key, value)
                if (not (self.expires < time.time())) or (self.expires == None):
                    self.authed = True
        except:
            pass

    def renew(self):
        # Renew session
        meower.db.sessions.update_one({"_id": self._id}, {"$set": {"expires": time.time() + self.expires}})
        self.expires = time.time() + self.expires
    
    def delete(self):
        # Delete session
        meower.db.sessions.delete_one({"_id": self._id})
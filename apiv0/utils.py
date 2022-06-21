from __main__ import meower
from datetime import datetime
import time
import string
import secrets
import pymongo
import requests
from threading import Thread

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

# Create ratelimit dictionary
ratelimit = {}

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

def check_for_spam(user, seconds=1):
    if user in ratelimit:
        if ratelimit[user] > int(time.time()):
            return True
    ratelimit[user] = int(time.time()) + seconds
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
        return requests.post("https://email-worker.meower.workers.dev", headers={"X-Auth-Token": meower.auth_keys["worker_token"]}, json=payload)

    template = {
        "personalizations": [{
            "to": [],
            "dkim_domain": "meower.org",
            "dkim_selector": "mailchannels",
            "dkim_private_key": meower.auth_keys["email_dkim"]
        }],
        "from": {
            "email": "no-reply@meower.org",
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

def database_template():
	# Create indexes
	meower.db.chats.create_index([("members", pymongo.ASCENDING), ("isPublic", pymongo.ASCENDING)])
	meower.db.chats.create_index([("members", pymongo.ASCENDING), ("isPublic", pymongo.ASCENDING)])
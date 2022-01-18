from cloudlink import CloudLink
from better_profanity import profanity
import sys
import os
import string
import random
import bcrypt
import json
from datetime import datetime
import time

"""

Meower Social Media Platform - Server Source Code

Dependencies:
* CloudLink >=0.1.7.4
* better-profanity
* bcrypt

"""
class files: # Storage API for... well... storing things.
    def __init__(self):
        self.dirpath = os.path.dirname(os.path.abspath(__file__)) + "/Meower"
        print("Files class ready.")
    
    def init_files(self):
        for directory in [
            "./Meower/",
            "./Meower/Storage",
            "./Meower/Storage/Posts",
            "./Meower/Storage/Categories",
            "./Meower/Storage/Categories/Home",
            "./Meower/Storage/Categories/Announcements",
            "./Meower/Storage/Categories/Threads",
            "./Meower/Userdata",
            "./Meower/Logs",
            "./Meower/Jail",
        ]:
            try:
                os.mkdir(directory)
            except FileExistsError:
                pass
    
    def write(self, fdir, fname, data):
        try:
            if os.path.exists(self.dirpath + "/" + fdir):
                #print("TYPE:", type(data))
                if type(data) == str:
                    f = open((self.dirpath + "/" + fdir + "/" + fname), "w")
                    f.write(data)
                    f.close()
                elif type(data) == dict:
                    f = open((self.dirpath + "/" + fdir + "/" + fname), "w")
                    f.write(json.dumps(data))
                    f.close()
                else:
                    f = open((self.dirpath + "/" + fdir + "/" + fname), "w")
                    f.write(str(data))
                    f.close()
                return True
            else:
                return False
        except Exception as e:
            print(e)
            return False
    
    def mkdir(self, directory):
        check1 = False
        try:
            os.makedirs((self.dirpath + "/" + directory), exist_ok=True)
            check1 = True
        except Exception as e:
            print(e)
            return False
    
    def rm(self, file):
        try:
            os.remove((self.dirpath + "/" + file))
            return True
        except Exception as e:
            print(e)
            return False
    
    def rmdir(self, directory):
        try:
            check1 = os.rmdir((self.dirpath + "/" + directory))
            if check1:
                return True
            else:
                return False, 2
        except Exception as e:
            print(e)
            return False, 1
    
    def read(self, fname):
        try:
            if os.path.exists(self.dirpath + "/" + fname):
                dataout = open(self.dirpath + "/" + fname).read()
                return True, dataout
            else:
                return False, None
        except Exception as e:
            print(e)
            return False, None
    
    def chkfile(self, file):
        try:
            return True, os.path.exists(self.dirpath + "/" + file)
        except Exception as e:
            return False, None
    
    def lsdir(self, directory):
        try:
            return True, os.listdir(self.dirpath + "/" +directory)
        except Exception as e:
            print(e)
            return False, None
    
    def chktype(self, directory, file):
        try:
            if os.path.isfile(self.dirpath + "/" + directory + "/" + file):
                return True, 1
            elif os.path.isdir(self.dirpath + "/" + directory + "/" + file):
                return True,  2
            else:
                return False, None
        except Exception as e:
            print(e)
            return False, None

class security: # Security API for generating/checking passwords, creating session tokens and authentication codes
    def __init__(self):
        self.bc = bcrypt
        self.fs = files()
        print("Security class ready.")
    
    def create_pswd(self, password, strength=12): # bcrypt hashes w/ salt
        if type(password) == str:
            if type(strength) == int:
                pswd_bytes = bytes(password, "utf-8")
                hashed_pw = self.bc.hashpw(pswd_bytes, self.bc.gensalt(strength))
                return hashed_pw.decode()
            else:
                error = "Strength parameter is not " + str(int) + ", got " + str(type(strength))
                raise TypeError(error)
        else:
            error = "Password parameter is not " + str(str) + ", got " + str(type(password))
            raise TypeError(error)
    
    def check_pswd(self, password, hashed_pw): # bcrypt checks
        if type(password) == str:
            if type(hashed_pw) == str:
                pswd_bytes = bytes(password, "utf-8")
                hashed_pw_bytes = bytes(hashed_pw, "utf-8")
                return self.bc.checkpw(pswd_bytes, hashed_pw_bytes)
            else:
                error = "Hashed password parameter is not " + str(str) + ", got " + str(type(hashed_pw))
                raise TypeError(error)
        else:
            error = "Password parameter is not " + str(str) + ", got " + str(type(password))
            raise TypeError(error)

    def gen_token(self): # Generates a unique session token.
        output = ""
        for i in range(50):
            output += random.choice('0123456789ABCDEFabcdef')
        return output

    def gen_key(self): # Generates a 6-digit key for Meower Authenticator.
        output = ""
        for i in range(6):
            output += random.choice('0123456789')
        return output

    def read_user_account(self, username): # Reads the contents of the username's account. Returns true if the account exists and has been read back correctly.
        if type(username) == str:
            result, dirlist = self.fs.lsdir("/Userdata/")
            if result:
                if str(username + ".json") in dirlist: # Read back the userfile
                    result2, payload = self.fs.read("/Userdata/" + str(username + ".json"))
                    if result2:
                        try:
                            return True, json.loads(payload)
                        except json.decoder.JSONDecodeError:
                            print(('Error while decoding user "{0}"'+"'s json data").format(username))
                            return False, None
                    else:
                        return False, None
                else:
                    return False, True
            else:
                return False, None
        else:
            return False, None
    
    def write_user_account(self, username, new_data): # Returns true if the account does not exist and has been generated successfully.
        if type(username) == str:
            result, dirlist = self.fs.lsdir("/Userdata/")
            if result:
                if str(username + ".json") in dirlist:
                    if type(new_data) == dict:
                        result2 = self.fs.write("/Userdata/", str(username + ".json"), json.dumps(new_data))
                        if result2:
                            pass
                        else:
                            print("Account modify err")
                        return True, result2 # Both true - Account modified OK, if result is false - Server error
                    else:
                        print("Account modifier datatype error")
                        return False, False # The datatype is not valid
                else:
                    print("Account does not exist")
                    return False, True # Account does not exist
            else:
                print("Account server error")
                return False, False # Server error
        else:
            print("Account server error")
            return False, False # Server error
    
    def gen_user_account(self, username): # Returns true if the account does not exist and has been generated successfully.
        if type(username) == str:
            result, dirlist = self.fs.lsdir("/Userdata/")
            if result:
                if not str(username + ".json") in dirlist:
                    tmp = {
                        "user_settings": {
                            "theme": "orange",
                            "mode": True,
                            "sfx": True,
                            "debug": False,
                            "bgm": True,
                            "bgm_song": "Voxalice - Percussion bass loop",
                            "layout": "new"
                        },
                        "user_data": {
                            "pfp_data": "1",
                            "quote": "" # User's quote
                        },
                        "secure_data": {
                            "email": "", # TODO: Add an Email bot for account recovery
                            "pswd": "", # STORE ONLY SALTED HASHES FOR PASSWORD, DO NOT STORE PLAINTEXT OR UNSALTED HASHES
                            "lvl": "0", # Account levels. 
                            "banned": False # Banned?
                        }
                    }
                    result2 = self.fs.write("/Userdata/", str(username + ".json"), json.dumps(tmp))
                    if result2:
                        pass
                    else:
                        print("Account gen err")
                    return True, result2 # Both true - Account generated OK, if result is false - Server error
                else:
                    return False, True # Account exists
            else:
                print("Account server error")
                return False, False # Server error
        else:
            print("Account server error")
            return False, False # Server error

class meower(files, security): # Meower Server itself
    def __init__(self, debug=False, ignoreUnauthedBlanks=False):
        self.cl = CloudLink(debug=debug)
        self.ignoreUnauthedBlanks = ignoreUnauthedBlanks
        
        # Add custom status codes to CloudLink
        self.cl.codes["KeyNotFound"] = "I:010 | Key Not Found"
        self.cl.codes["PasswordInvalid"] = "I:011 | Invalid Password"
        self.cl.codes["GettingReady"] = "I:012 | Getting ready"
        self.cl.codes["ObsoleteClient"] = "I:013 | Client is out-of-date or unsupported"
        self.cl.codes["Pong"] = "I:014 | Pong"
        self.cl.codes["IDExists"] = "I:015 | Account exists"
        self.cl.codes["2FAOnly"] = "I:016 | 2FA Required"
        self.cl.codes["MissingPermissions"] = "I:017 | Missing permissions"
        self.cl.codes["Banned"] = "E:018 | Account Banned"
        
        clear_cmd = "clear" # Change for os-specific console clear
        # Instanciate the other classes into Meower
        self.fs = files()
        self.secure = security()
        
        # init the filesystem
        self.fs.init_files()
        
        # Peak number of users logger
        self.peak_users_logger = {
            "count": 0,
            "timestamp": {
                "mo": 0,
                "d": 0,
                "y": 0,
                "h": 0,
                "mi": 0,
                "s": 0
            }
        }
        
        # create a list of supported versions
        self.versions_supported = [
            "scratch-beta-4.8",
            "scratch-beta-5.2",
            "scratch-beta-5.3",
            "scratch-beta-5.4",
            "meower-mobile-0.4_3"
        ]
    
        self.cl.callback("on_packet", self.on_packet)
        self.cl.callback("on_close", self.on_close)
        self.cl.callback("on_connect", self.on_connect)
        self.cl.trustedAccess(True, [
            "meower", # Do not modify key
            "1gr3grthsg2htgfhsz24u4uy46tggsv2wytuy354hg3u75i57b3u5tgu35hsdfth24673244y2"
        ])
    
        self.cl.loadIPBlocklist([
            '127.0.0.1'
        ])
        
        self.cl.setMOTD("Meower Social Media Platform Server", enable=True)
        time.sleep(1)
        os.system(clear_cmd+" && echo Meower Social Media Platform Server")
        time.sleep(1)
        self.cl.server(port=3000, ip="0.0.0.0")
    
    def log(self, event):
        today = datetime.now()
        now = today.strftime("%m/%d/%Y %H:%M.%S")
        print("{0}: {1}".format(now, event))

    def get_client_statedata(self, client): # "steals" information from the CloudLink module to get better client data
        if type(client) == str:
            client = self.cl._get_obj_of_username(client)
        if not client == None:
            if client['id'] in self.cl.statedata["ulist"]["objs"]:
                tmp = self.cl.statedata["ulist"]["objs"][client['id']]
                return tmp
            else:
                return None
    
    def modify_client_statedata(self, client, key, newvalue): # WARN: Use with caution: DO NOT DELETE UNNECESSARY KEYS!
        if type(client) == str:
            client = self.cl._get_obj_of_username(client)
        if not client == None:
            if client['id'] in self.cl.statedata["ulist"]["objs"]:
                try:
                    self.cl.statedata["ulist"]["objs"][client['id']][key] = newvalue
                    return True
                except Exception as e:
                    print(e)
                    return False
            else:
                return False
    
    def delete_client_statedata(self, client, key): # WARN: Use with caution: DO NOT DELETE UNNECESSARY KEYS!
        if type(client) == str:
            client = self.cl._get_obj_of_username(client)
        if not client == None:
            if client['id'] in self.cl.statedata["ulist"]["objs"]:
                if key in self.cl.statedata["ulist"]["objs"][client['id']]:
                    try:
                        del self.cl.statedata["ulist"]["objs"][client['id']][key]
                        return True
                    except Exception as e:
                        print(e)
                        return False
            else:
                return False
    
    def update_home(self, new_data):
        status, payload = self.get_home()
        today = datetime.now()
        today = str(today.strftime("%d%m%Y"))
        if status != 0:
            result = self.fs.write("/Storage/Categories/Home/", today, new_data)
            return result
        else:
            return False
    
    def get_home(self):
        today = datetime.now()
        today = str(today.strftime("%d%m%Y"))
        result, dirlist = self.fs.lsdir("/Storage/Categories/Home/")
        if result:
            if today in dirlist:
                result2, payload = self.fs.read(str("/Storage/Categories/Home/" + today))
                if result2:
                    return 2, payload
                else:
                    return 0, None
            else:
                result2 = self.fs.write("/Storage/Categories/Home/", today, "")
                if result2:
                    return 1, ""
                else:
                    return 0, None
        else:
            return 0, None, None
    
    def on_close(self, client):
        if type(client) == dict:
            self.log("{0} Disconnected.".format(client["id"]))
        elif type(client) == str:
            self.log("{0} Logged out.".format(self.cl._get_username_of_obj(client)))
        self.log_peak_users()
       
    def on_connect(self, client):
        self.log("{0} Connected.".format(client["id"]))
        self.modify_client_statedata(client, "authtype", "")
        self.modify_client_statedata(client, "authed", False)
        
        # Rate limiter
        today = datetime.now()
        self.modify_client_statedata(client, "last_packet", {
            "h": today.strftime("%H"),
            "m": today.strftime("%M"),
            "s": today.strftime("%S")
        })
    
    def log_peak_users(self):
        current_users = len(self.cl.getUsernames())
        if current_users > self.peak_users_logger["count"]:
            today = datetime.now()
            self.peak_users_logger = {
                "count": current_users,
                "timestamp": {
                    "mo": (datetime.now()).strftime("%m"),
                    "d": (datetime.now()).strftime("%d"),
                    "y": (datetime.now()).strftime("%Y"),
                    "h": (datetime.now()).strftime("%H"),
                    "mi": (datetime.now()).strftime("%M"),
                    "s": (datetime.now()).strftime("%S")
                }
            }
            self.log("New peak in # of concurrent users! {0}".format(current_users))
            payload = {
                "mode": "peak",
                "payload": self.peak_users_logger
            }
            self.cl.sendPacket({"cmd": "direct", "val": payload})
    
    def check_for_spam(self, client):
        today = datetime.now()
        current_time = int(today.strftime("%H%M%S"))
        self.log("Current time is {0}".format(current_time))
        not_formatter = self.get_client_statedata(client)["last_packet"]
        formatter = not_formatter["h"] + not_formatter["m"] + not_formatter["s"]
        self.log("Last timestamp for user post was {0}".format(formatter))
        return (int(formatter) <= (current_time + 1))
    
    def on_packet(self, message):
        id = message["id"]
        val = message["val"]
        if type(message["id"]) == dict:
            ip = self.cl.getIPofObject(message["id"])
            client = message["id"]
            clienttype = 0
        elif type(message["id"]) == str:
            ip = self.cl.getIPofUsername(message["id"])
            client = self.cl._get_obj_of_username(message["id"])
            clienttype = 1
        
        if "cmd" in message:    
            cmd = message["cmd"]
            
            # General networking stuff
            
            if cmd == "ping":
                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Pong"], "id": id})
            
            elif cmd == "version_chk":
                if type(val) == str:
                    if val in self.versions_supported:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["ObsoleteClient"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
            
            # moderator stuff
            
            elif cmd == "block":
                if (self.get_client_statedata(id)["authed"]):
                    try:
                        result, payload = self.secure.read_user_account(id)
                        if result:
                            self.log("RCS: {0}'s account level is {1}".format(id, str(payload["secure_data"]["lvl"])))
                            if int(payload["secure_data"]["lvl"]) >= 2:
                                if type(val) == str:
                                    self.log("Blocking IP {0}".format(val))
                                    self.cl.blockIP(val)
                                    self.cl.sendPacket({"cmd": "direct", "val": "", "id": id})
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": id})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": id})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["MissingPermissions"], "id": id})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                    except Exception as e:
                        self.log("Error: {0}".format(e))
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": id})
            
            elif cmd == "kick":
                if (self.get_client_statedata(id)["authed"]):
                    try:
                        result, payload = self.secure.read_user_account(id)
                        if result:
                            self.log("RCS: {0}'s account level is {1}".format(id, str(payload["secure_data"]["lvl"])))
                            if int(payload["secure_data"]["lvl"]) >= 1:
                                if type(val) == str:
                                    ip = self.cl.getIPofUsername(val)
                                    self.log("Kicking {0}".format(val))
                                    self.cl.kickClient(val)
                                    self.cl.sendPacket({"cmd": "direct", "val": "", "id": id})
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": id})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["MissingPermissions"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                    except Exception as e:
                        self.log("Error: {0}".format(e))
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "clear_home":
                if (self.get_client_statedata(id)["authed"]):
                    try:
                        result, payload = self.secure.read_user_account(id)
                        if result:
                            self.log("RCS: {0}'s account level is {1}".format(id, str(payload["secure_data"]["lvl"])))
                            if int(payload["secure_data"]["lvl"]) >= 1:
                                today = datetime.now()
                                today = str(today.strftime("%d%m%Y"))
                                result = self.fs.write("/Storage/Categories/Home/", today, "")
                                self.log("cleared home")
                                self.cl.sendPacket({"cmd": "direct", "val": "", "id": id})
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": id})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["MissingPermissions"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                    except Exception as e:
                        self.log("Error: {0}".format(e))
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
        
            elif cmd == "get_statedata":
                if (self.get_client_statedata(id)["authed"]):
                    try:
                        result, payload = self.secure.read_user_account(id)
                        if result:
                            self.log("RCS: {0}'s account level is {1}".format(id, str(payload["secure_data"]["lvl"])))
                            if int(payload["secure_data"]["lvl"]) == 4:
                                tmp_statedata = self.cl.statedata.copy()
                                tmp_statedata.pop("ulist")
                                tmp_statedata.pop("trusted")
                                tmp_statedata.pop("gmsg")
                                tmp_statedata.pop("motd_enable")
                                tmp_statedata.pop("motd")
                                tmp_statedata.pop("secure_enable")
                                tmp_statedata.pop("secure_keys")
                                tmp_statedata["users"] = self.cl.getUsernames()
                                self.cl.sendPacket({"cmd": "direct", "val": tmp_statedata, "id": id})
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": id})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["MissingPermissions"], "id": id})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                    except Exception as e:
                        self.log("Error at get_statedata: {0}".format(e))
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": id})
            
            elif cmd == "get_user_ip":
                if (self.get_client_statedata(id)["authed"]):
                    try:
                        result, payload = self.secure.read_user_account(id)
                        if result:
                            self.log("RCS: {0}'s account level is {1}".format(id, str(payload["secure_data"]["lvl"])))
                            if int(payload["secure_data"]["lvl"]) >= 1:
                                if type(val) == str:
                                    self.cl.sendPacket({"cmd": "direct", "val": {"username": str(val), "ip": str(self.cl.getIPofUsername(val))}, "id": id})
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": id})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": id})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["MissingPermissions"], "id": id})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                    except Exception as e:
                        self.log("Error at get_statedata: {0}".format(e))
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": id})
            
            elif cmd == "get_user_data":
                if (self.get_client_statedata(id)["authed"]):
                    try:
                        result, payload = self.secure.read_user_account(id)
                        if result:
                            self.log("RCS: {0}'s account level is {1}".format(id, str(payload["secure_data"]["lvl"])))
                            if int(payload["secure_data"]["lvl"]) >= 1:
                                if type(val) == str:
                                    try:
                                        result, payload = self.secure.read_user_account(val)
                                        if result:
                                            payload["secure_data"].pop("pswd")
                                            
                                            payload2 = {
                                                "username": str(val),
                                                "payload": payload
                                            }
                                            
                                            self.log("Fetching user {0}'s account data".format(val))
                                            self.cl.sendPacket({"cmd": "direct", "val": payload2, "id": id})
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": id})
                                        else:
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                                    except Exception as e:
                                        self.log("Error: {0}".format(e))
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": id})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["MissingPermissions"], "id": id})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                    except Exception as e:
                        self.log("Error at get_statedata: {0}".format(e))
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": id})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": id})
            
            elif cmd == "ban":
                if (self.get_client_statedata(id)["authed"]):
                    try:
                        result, payload = self.secure.read_user_account(id)
                        if result:
                            self.log("RCS: {0}'s account level is {1}".format(id, str(payload["secure_data"]["lvl"])))
                            if int(payload["secure_data"]["lvl"]) >= 1:
                                if type(val) == str:
                                    self.log("Attempting to ban {0}".format(val))
                                    result, payload = self.secure.read_user_account(val)
                                    if result:
                                        payload["secure_data"]["banned"] = True
                                        result2, code2 = self.secure.write_user_account(val, payload)
                                        if result2:
                                            self.log("Banned {0}, now kicking...".format(val))
                                            self.cl.kickClient(val)
                                            self.cl.sendPacket({"cmd": "direct", "val": "", "id": id})
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": id})
                                    else:
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["MissingPermissions"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                    except Exception as e:
                        self.log("Error: {0}".format(e))
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "pardon":
                if (self.get_client_statedata(id)["authed"]):
                    try:
                        result, payload = self.secure.read_user_account(id)
                        if result:
                            self.log("RCS: {0}'s account level is {1}".format(id, str(payload["secure_data"]["lvl"])))
                            if int(payload["secure_data"]["lvl"]) >= 1:
                                if type(val) == str:
                                    self.log("Attempting to pardon {0}".format(val))
                                    result, payload = self.secure.read_user_account(val)
                                    if result:
                                        payload["secure_data"]["banned"] = False
                                        result2, code2 = self.secure.write_user_account(val, payload)
                                        if result2:
                                            self.log("Pardoned {0}.".format(val))
                                            self.cl.sendPacket({"cmd": "direct", "val": "", "id": id})
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": id})
                                    else:
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["MissingPermissions"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                    except Exception as e:
                        self.log("Error: {0}".format(e))
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            # Security and account stuff
            
            elif cmd == "authpswd":
                if (self.get_client_statedata(id)["authtype"] == "") or (self.get_client_statedata(id)["authtype"] == "pswd"):
                    if not self.get_client_statedata(id)["authed"]:
                        if type(val) == dict:
                            result, payload = self.secure.read_user_account(val["username"])
                            if result:
                                if ("banned" in payload["secure_data"]) and (payload["secure_data"]["banned"]):
                                    # User banned.
                                    self.log("{0} not authed: Account banned.".format(val["username"]))
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Banned"], "id": message["id"]})
                                else:
                                    hashed_pswd = payload["secure_data"]["pswd"]
                                    if not hashed_pswd == "":
                                        self.modify_client_statedata(id, "authtype", "pswd")
                                        valid_auth = self.secure.check_pswd(val["pswd"], hashed_pswd)
                                        #print(valid_auth)
                                        if valid_auth:
                                            self.log("{0} is authed".format(val["username"]))
                                            self.modify_client_statedata(id, "authtype", "pswd")

                                            # The client is authed
                                            self.modify_client_statedata(id, "authed", True)

                                            payload2 = {
                                                "mode": "auth",
                                                "payload": {
                                                    "username": val["username"]
                                                }
                                            }
                                            
                                            # Check for clients that are trying to steal the ID and kick em' / Disconnect other sessions
                                            if val["username"] in self.cl.getUsernames():
                                                self.log("Detected someone trying to use the username {0} wrongly".format(val["username"]))
                                                self.cl.kickClient(val["username"])
                                            
                                            # really janky code that automatically sets user ID
                                            if self.get_client_statedata(id)["type"] != "scratch": # Prevent this from breaking compatibility with scratch clients
                                                self.modify_client_statedata(id, "username", val["username"])
                                                self.cl.statedata["ulist"]["usernames"][val["username"]] = id["id"]
                                                self.cl.sendPacket({"cmd": "ulist", "val": self.cl._get_ulist()})
                                                self.log("{0} autoID given".format(val["username"]))
                                            
                                            self.cl.sendPacket({"cmd": "direct", "val": payload2, "id": message["id"]})
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                                            self.log_peak_users()
                                        else:
                                            self.log("{0} not authed".format(val["username"]))
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["PasswordInvalid"], "id": message["id"]})
                            else:
                                if type(payload) == bool:
                                    self.log("{0} not found in accounts".format(val["username"]))
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["IDNotFound"], "id": message["id"]})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                    else:
                        self.log("{0} is already authed".format(id))
                        payload2 = {
                            "mode": "auth",
                            "payload": {
                                "username": val["username"]
                            }
                        }
                        self.cl.sendPacket({"cmd": "direct", "val": payload2, "id": message["id"]})
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "get_profile":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    if clienttype == 1:
                        if type(val) == str:
                            result, payload = self.secure.read_user_account(val)
                            if result: # Format message for meower
                                payload["lvl"] = payload["secure_data"]["lvl"] # Make the user's level read-only
                                payload.pop("secure_data") # Remove the user's secure data
                                if str(val) != str(id): # Purge sensitive data if the specified ID isn't the same
                                    payload.pop("user_settings") # Remove user's settings
                                payload["user_id"] = str(val) # Report user ID for profile
                                payload = {
                                    "mode": "profile",
                                    "payload": payload
                                }
                                self.log("{0} fetching profile {1}".format(id, val))
                            if result:
                                self.cl.sendPacket({"cmd": "direct", "val": payload, "id": message["id"]})
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["IDNotFound"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "gen_account":
                if (((self.get_client_statedata(id)["authtype"] == "") and (not self.get_client_statedata(id)["authed"])) or ((self.get_client_statedata(id)["authtype"] == "2fa") and (self.get_client_statedata(id)["authed"]))):
                    if clienttype == 1:
                        # Generate the user account
                        result, code = self.secure.gen_user_account(id)
                        if result and code:
                            
                            # Since the account was just created, add auth info, if the account was made using a password then generate hash and store it
                            if (not self.get_client_statedata(id)["authtype"] == "") or (not self.get_client_statedata(id)["authtype"] == "2fa"):
                                if type(val) == str:
                                    
                                    # Generate a hash for the password
                                    hashed_pswd = self.secure.create_pswd(val)
                                    
                                    # Store the hash in the account's file
                                    result, payload = self.secure.read_user_account(id)
                                    
                                    if result:
                                        payload["secure_data"]["pswd"] = hashed_pswd
                                        result2, code2 = self.secure.write_user_account(id, payload)
                                        if result2:
                                            payload2 = {
                                                "mode": "auth",
                                                "payload": ""
                                            }
                                            
                                            # The client is authed
                                            self.log("{0} is authed w/ new account generated".format(id))
                                            self.modify_client_statedata(id, "authed", True)
                                            
                                            self.cl.sendPacket({"cmd": "direct", "val": payload2, "id": message["id"]})
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                                        else:
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                                    else:
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Syntax"], "id": message["id"]})
                            
                        else:
                            if (not result) and code:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["IDExists"], "id": message["id"]})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["IDRequired"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "update_config":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    if clienttype == 1:
                        if type(val) == dict:
                            result, payload = self.secure.read_user_account(id)
                            if result: # Format message for meower
                                for config in val:
                                    if config in payload:
                                        if (not "lvl" in config) or (not "pswd" in config):
                                            payload[config] = val[config]
                                result2, payload2 = self.secure.write_user_account(id, payload)
                                if result2:
                                    payload3 = {
                                        "mode": "cfg",
                                        "payload": ""
                                    }
                                    self.log("{0} Updating their config".format(id))
                                    self.cl.sendPacket({"cmd": "direct", "val": payload3, "id": message["id"]})
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["IDNotFound"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            # General chat stuff
            
            elif cmd == "get_peak_users":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    payload = {
                        "mode": "peak",
                        "payload": self.peak_users_logger
                    }
                    self.cl.sendPacket({"cmd": "direct", "val": payload, "id": message["id"]})
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "set_livechat_state":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    if "mode" in val:
                        if type(val["mode"]) == int:
                            state = {
                                "mode": val["mode"]
                            }
                            if clienttype == 0:
                                state["u"] = ""
                            else:
                                state["u"] = id
                                
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                            
                            # Broadcast the state to all listening clients
                            #print(state)
                            self.log("{0} modifying livechat state to {1}".format(id, val["mode"]))
                            self.cl.sendPacket({"cmd": "direct", "val": state})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Syntax"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "post_livechat":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    if type(val) == str:
                        if (not len(val) >= 360):
                            if self.check_for_spam(id):
                                today = datetime.now()
                                
                                # Run word filter against post data
                                post = profanity.censor(val)
                                
                                # Attach metadata to post
                                post_w_metadata = {
                                    "t": {
                                        "mo": (datetime.now()).strftime("%m"),
                                        "d": (datetime.now()).strftime("%d"),
                                        "y": (datetime.now()).strftime("%Y"),
                                        "h": (datetime.now()).strftime("%H"),
                                        "mi": (datetime.now()).strftime("%M"),
                                        "s": (datetime.now()).strftime("%S"),
                                    },
                                    "p": post
                                }
                                if clienttype == 0:
                                    post_w_metadata["u"] = ""
                                else:
                                    post_w_metadata["u"] = id
                                    
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                                 
                                # Broadcast the post to all listening clients
                                relay_post = post_w_metadata
                                relay_post["mode"] = 2
                                self.log("{0} posting livechat message".format(id))
                                #print(relay_post)
                                self.cl.sendPacket({"cmd": "direct", "val": relay_post})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["RateLimit"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["TooLarge"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "post_home":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    if type(val) == str:
                        if (not len(val) >= 360):
                            if self.check_for_spam(id):
                                today = datetime.now()
                                # Generate a post ID
                                post_id = str(today.strftime("%d%m%Y%H%M%S")) 
                                if clienttype == 0:
                                    post_id = "-" + post_id
                                else:
                                    post_id = id + "-" + post_id
                                
                                # Run word filter against post data
                                post = profanity.censor(val)
                                
                                # Attach metadata to post
                                post_w_metadata = {
                                    "t": {
                                        "mo": (datetime.now()).strftime("%m"),
                                        "d": (datetime.now()).strftime("%d"),
                                        "y": (datetime.now()).strftime("%Y"),
                                        "h": (datetime.now()).strftime("%H"),
                                        "mi": (datetime.now()).strftime("%M"),
                                        "s": (datetime.now()).strftime("%S"),
                                    },
                                    "p": post
                                }
                                if clienttype == 0:
                                    post_w_metadata["u"] = ""
                                else:
                                    post_w_metadata["u"] = id
                                
                                # Read back current homepage state (and create a new homepage if needed)
                                status, payload = self.get_home()
                                
                                # Check status of homepage
                                if status != 0:
                                    # Update the current homepage
                                    new_home = str(payload + post_id + ";")
                                    result = self.update_home(new_home)
                                    
                                    if result:
                                        # Store the post
                                        result2 = self.fs.write("/Storage/Posts", post_id, post_w_metadata)
                                        if result2:
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                                            
                                            # Broadcast the post to all listening clients
                                            
                                            relay_post = post_w_metadata
                                            relay_post["mode"] = 1
                                            relay_post["post_id"] = str(post_id)
                                            #print(relay_post)
                                            self.log("{0} posting home message {1}".format(id, post_id))
                                            self.cl.sendPacket({"cmd": "direct", "val": relay_post})
                                        else:
                                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                                    else:
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["RateLimit"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["TooLarge"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "get_post":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    if type(val) == str:
                        # Check for posts in storage
                        result, payload = self.fs.read("/Storage/Posts/" + val)
                        
                        if result: # Format message for meower
                            # Temporarily convert the JSON string to Dict to add the post ID data to it
                            tmp_payload = json.loads(payload)
                            tmp_payload["post_id"] = val
                            payload = json.dumps(tmp_payload)
                            
                            payload = {
                                "mode": "post",
                                "payload": json.loads(payload)
                            }
                        if result:
                            self.log("{0} getting home message {1}".format(id, tmp_payload["post_id"]))
                            self.cl.sendPacket({"cmd": "direct", "val": payload, "id": message["id"]})
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "get_home":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    status, payload = self.get_home()
                    
                    if status != 0: # Format message for meower
                        payload = {
                            "mode": "home",
                            "payload": payload
                        }
                    self.log("{0} getting home index".format(id))
                    
                    if status == 0: # Home error
                        self.log("Error while generating homepage")
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                    elif status == 1: # Home was generated
                        self.cl.sendPacket({"cmd": "direct", "val": payload, "id": message["id"]})
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                    elif status == 2: # Home already generated
                        self.cl.sendPacket({"cmd": "direct", "val": payload, "id": message["id"]})
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            else:
                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Invalid"], "id": message["id"]})
        else:
            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Syntax"], "id": message["id"]})
        
        # Rate limiter
        today = datetime.now()
        self.modify_client_statedata(client, "last_packet", {
            "h": today.strftime("%H"),
            "m": today.strftime("%M"),
            "s": today.strftime("%S")
        })
    
if __name__ == "__main__":
    meower(debug = False, ignoreUnauthedBlanks = False) # Runs the server

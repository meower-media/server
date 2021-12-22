from cloudlink import CloudLink
from scratch2py import Scratch2Py
from better_profanity import profanity
import sys
import os
import string
import random
import bcrypt
import json
from datetime import datetime

SCRATCH_UNAME = "" # PUT A SCRATCH USERNAME HERE THAT HAS SCRATCHER STATUS
SCRATCH_PSWD = "" # PUT SCRATCH PASSWORD HERE, DO NOT SHARE IN PRODUCTION

"""

Meower Social Media Platform - Server Source Code

Dependencies:
* CloudLink >=0.1.7.4
* better-profanity
* bcrypt
* scratch2py

"""
class files: # Storage API for... well... storing things.
    def __init__(self):
        self.dirpath = os.path.dirname(os.path.abspath(__file__)) + "/Meower"
        self.defaultsecparams = {
            "isHidden": False,
            "isSecure": False,
            "accessKey": "",
            "limitProjectAccess": False,
            "permittedProjectIDs": {}
           }
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
            "./Meower/Userdata"
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
        if check1:
            try:
                if os.path.exists(self.dirpath + "/" + directory):
                    with open((self.dirpath + "/" + directory + "/SECURITY.json"), "w") as f:
                        json.dump(self.defaultsecparams, f)
                    return True
                else:
                    return False
            except Exception as e:
                print(e)
                return False
        else:
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
            check1 = self.deletefile((directory + "/SECURITY.json"))
            if check1:
                os.rmdir((self.dirpath + "/" + directory))
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
    
    def create_pswd(self, password, strength=15): # bcrypt hashes w/ salt, TODO: add pepper and use a stronger default strength
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
                            "bgm_song": "Voxalice - Percussion bass loop"
                        },
                        "user_data": {
                            "pfp_type": "",
                            "pfp_data": ""
                        },
                        "lvl": "", # Account level, 0:Normal member, 1:Admin, 2:On-Watch
                        "quote": "", # User's quote
                        "pswd": "", # STORE ONLY SALTED HASHES FOR PASSWORD, DO NOT STORE PLAINTEXT OR UNSALTED HASHES
                        "email": "" # TODO: Add an Email bot for account recovery
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
    def __init__(self, debug=False, autoAuth=False, runAuth=True, ignoreUnauthedBlanks=False):
        self.cl = CloudLink(debug=debug)
        self.ignoreUnauthedBlanks = ignoreUnauthedBlanks
        
        # Add custom status codes to CloudLink
        self.cl.codes["KeyNotFound"] = "I:010 | Key Not Found"
        self.cl.codes["PasswordInvalid"] = "I:011 | Invalid Password"
        self.cl.codes["GettingReady"] = "I:012 | Getting ready"
        self.cl.codes["ObsoleteClient"] = "I:013 | Client is out-of-date"
        self.cl.codes["Pong"] = "I:014 | Pong"
        self.cl.codes["IDExists"] = "I:015 | Account exists"
        self.cl.codes["2FAOnly"] = "I:016 | 2FA Required"
        
        clear_cmd = "cls" # Change for os-specific console clear
        # Instanciate the other classes into Meower
        self.fs = files()
        self.secure = security()
        
        # init the filesystem
        self.fs.init_files()
        
        if runAuth:
            if autoAuth:
                try:
                    os.system(clear_cmd+" && echo Please wait...")
                    self.s2py = Scratch2Py(str(SCRATCH_UNAME), str(SCRATCH_PSWD))
                    self.authenticator = self.s2py.scratchConnect("561076533")
                    print("Session ready.")
                except Exception as e:
                    print("Session error! {0}".format(e))
                    sys.exit()
            else:
                try: # Authenticate session for use with verifying Scratchers using 2-Factor Authentication           
                    os.system(clear_cmd+"&& echo Please login to Scratch to start 2-Factor Authenticator.")
                    self.s2py = Scratch2Py(str(input("Enter your Scratch username: ")), str(input("Enter password: ")))
                    self.authenticator = self.s2py.scratchConnect("561076533")
                    print("Session ready.")
                except Exception as e:
                    print("Session error! {0}".format(e))
                    sys.exit()
    
        self.cl.callback("on_packet", self.on_packet)
        self.cl.callback("on_close", self.on_close)
        self.cl.callback("on_connect", self.on_connect)
        self.cl.trustedAccess(True, [
            "meower" # DO NOT USE THIS KEY IN PRODUCTION
        ])
    
        self.cl.loadIPBlocklist([
            '127.0.0.1',
        ])
    
        self.cl.setMOTD("Meower Social Media Platform - Prototype Server", enable=True)
        os.system(clear_cmd+" && echo Meower Social Media Platform - Prototype Server")
        self.cl.server()
    
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
    
    def on_close(self, client): # TODO: Write code that can tell clients that someone has disconnected
        #print("Client disconnected:", client["id"])
        pass
    
    def on_connect(self, client): # TODO: Write code that can tell clients that someone has connected
        self.modify_client_statedata(client, "authtype", "")
        self.modify_client_statedata(client, "authed", False)
    
    def on_packet(self, message): # TODO: Add authentication, storage, and GET/PUT-style storage implementation
        id = message["id"]
        val = message["val"]
        if type(message["id"]) == dict:
            ip = self.cl.getIPofObject(message["id"])
            clienttype = 0
        elif type(message["id"]) == str:
            ip = self.cl.getIPofUsername(message["id"])
            clienttype = 1
        if "cmd" in message:    
            cmd = message["cmd"]
            
            # TODO: Add ratelimiter and IP anti-spam blocker
            # TODO: Implement a password-based authentication system that doesn't suck a duck
            """if cmd == "block":
                self.cl.blockIP(ip)
                self.cl.untrust(id)
                print("Blocking IP", ip)
                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["TALostTrust"], "id": message["id"]})
            elif cmd == "pardon":
                self.cl.unblockIP(message["val"])
                print("Unblocking IP", ip)
                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})"""
            
            # General networking stuff
            
            if cmd == "ping":
                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Pong"], "id": id})
            
            # Security and account stuff
            
            elif cmd == "authpswd":
                if (self.get_client_statedata(id)["authtype"] == "") or (self.get_client_statedata(id)["authtype"] == "pswd"):
                    if not self.get_client_statedata(id)["authed"]:
                        if type(val) == dict:
                            result, payload = self.secure.read_user_account(val["username"])
                            if result:
                                hashed_pswd = payload["pswd"]
                                if not hashed_pswd == "":
                                    self.modify_client_statedata(id, "authtype", "pswd")
                                    valid_auth = self.secure.check_pswd(val["pswd"], hashed_pswd)
                                    #print(valid_auth)
                                    if valid_auth:
                                        print("{0} is authed".format(val["username"]))
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
                                            print("detected someone trying to use the username {0} wrongly".format(val["username"]))
                                            self.cl.kickClient(val["username"])

                                        self.cl.sendPacket({"cmd": "direct", "val": payload2, "id": message["id"]})
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                                    else:
                                        print("{0} not authed".format(val["username"]))
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["PasswordInvalid"], "id": message["id"]})
                                else:
                                    print("{0} not authed: Attempted to sign into an account created with 2FA".format(val["username"]))
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["2FAOnly"], "id": message["id"]})
                            else:
                                if type(payload) == bool:
                                    print("{0} not found in accounts".format(val["username"]))
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["IDNotFound"], "id": message["id"]})
                                else:
                                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                    else:
                        print("{0} is already authed".format(id))
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
            
            elif cmd == "auth2fa":
                if (self.get_client_statedata(id)["authtype"] == "") or (self.get_client_statedata(id)["authtype"] == "2fa"):
                    if not "key" in self.get_client_statedata(id):
                        # Generate a new authentication key
                        keygen = self.secure.gen_key()
                        
                        # Modify client's memory object to store the key for authentication
                        self.modify_client_statedata(id, "authtype", "2fa")
                        self.modify_client_statedata(id, "key", str(keygen))
                        
                        # Send a status code and the key to the client
                        self.cl.sendPacket({"cmd": "direct", "val": {"mode": "auth", "payload": str(keygen)}, "id": message["id"]})
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                    elif not self.get_client_statedata(id)["key"] == "":
                        # Resend the keygen
                        self.cl.sendPacket({"cmd": "direct", "val": {"mode": "auth", "payload": str(self.get_client_statedata(id)["key"])}, "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "checkauth":
                if self.get_client_statedata(id)["authtype"] == "2fa":
                    if self.get_client_statedata(id)["authed"] == False:
                        # Get the current authentication username list
                        auths = self.authenticator.readCloudVar(10)
                        # Create temporary variables for handling the authentication
                        tmp_auths = []
                        user_authed = False
                        user_valid_id = ""
                        tokengen = ""
                        if type(auths) == list:
                            # Convert the auth data into a list of potential keys sent from authenticator
                            for entry in auths:
                                if entry["name"] == "☁ AUTH":
                                    tmp_auths.append({"user": entry["user"], "val": entry["value"]})
                            # Check client memory object data's key against list of keys
                            if not self.get_client_statedata(id) == None:
                                for request in tmp_auths:
                                    if request["val"] == self.get_client_statedata(id)["key"]:
                                        print("Client {0} has been authenticated as {1}".format(id["id"], request["user"]))
                                        if not user_authed:
                                            # Delete the key as it is no longer needed in memory
                                            self.delete_client_statedata(id, "key")
                                            
                                            # The client is authed
                                            self.modify_client_statedata(id, "authed", True)
                                            
                                            # Get out of this loop and return data back to the client
                                            user_authed = True
                                            user_valid_id = request["user"]
                                            
                                            # Check for clients that are trying to steal the ID and kick em' / Disconnect other sessions
                                            if user_valid_id in self.cl.getUsernames():
                                                print("detected someone trying to use the username {0} wrongly".format(user_valid_id))
                                                self.cl.kickClient(user_valid_id)
                                            
                                            break
                            else:
                                print("Error: Client memory object not found")
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                                return
                            
                            # Tell the client that it has a valid id or not
                            if user_authed:
                                #print(self.get_client_statedata(id))
                                
                                # Generate an account for the user if not made
                                result, code = self.secure.gen_user_account(user_valid_id)
                                #print(result, code)
                                if result:
                                    if code:
                                        print("{0} is authed w/ new account generated".format(user_valid_id))
                                        self.cl.sendPacket({"cmd": "direct", "val": {"mode": "auth", "payload": {"username": str(user_valid_id), "is_new": True}}, "id": message["id"]})
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                                    else:
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                                else:
                                    if code:
                                        print("{0} is authed".format(user_valid_id))
                                        self.cl.sendPacket({"cmd": "direct", "val": {"mode": "auth", "payload": {"username": str(user_valid_id), "is_new": False}}, "id": message["id"]})
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                                    else:
                                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["KeyNotFound"], "id": message["id"]})
                            
                        else:
                            print("Error")
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                    else:
                       self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]}) 
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "get_profile":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    if clienttype == 1:
                        if type(val) == str:
                            result, payload = self.secure.read_user_account(val)
                            if result: # Format message for meower
                                payload.pop("pswd") # Remove the password hash from message (why the duck would we want to send back the password)
                                if str(val) != str(id): # Purge sensitive data if the specified ID isn't the same
                                    payload.pop("user_settings") # Remove the user's settings
                                    payload.pop("email") # Remove the user's email
                                payload = {
                                    "mode": "profile",
                                    "payload": payload
                                }
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
                                        payload["pswd"] = hashed_pswd
                                        result2, code2 = self.secure.write_user_account(id, payload)
                                        if result2:
                                            payload2 = {
                                                "mode": "auth",
                                                "payload": ""
                                            }
                                            
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
                                #print(payload)
                                #print(val)
                                for config in val:
                                    #print(config, val[config])
                                    if config in payload:
                                        payload[config] = val[config]
                                #print(payload)
                                result2, payload2 = self.secure.write_user_account(id, payload)
                                if result2:
                                    payload3 = {
                                        "mode": "cfg",
                                        "payload": ""
                                    }
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
                            self.cl.sendPacket({"cmd": "direct", "val": state})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Datatype"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Syntax"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "post_livechat":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
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
                    #print(relay_post)
                    self.cl.sendPacket({"cmd": "direct", "val": relay_post})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "post_home":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
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
                                #print(relay_post)
                                
                                self.cl.sendPacket({"cmd": "direct", "val": relay_post})
                            else:
                                self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                        else:
                            self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
                else:
                    self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["Refused"], "id": message["id"]})
            
            elif cmd == "get_post":
                if (self.get_client_statedata(id)["authed"]) or (self.ignoreUnauthedBlanks):
                    # Check for posts in storage
                    result, payload = self.fs.read("/Storage/Posts/" + val)
                    
                    if result: # Format message for meower
                        payload = {
                            "mode": "post",
                            "payload": json.loads(payload)
                        }
                    
                    if result:
                        self.cl.sendPacket({"cmd": "direct", "val": payload, "id": message["id"]})
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["OK"], "id": message["id"]})
                    else:
                        self.cl.sendPacket({"cmd": "statuscode", "val": self.cl.codes["InternalServerError"], "id": message["id"]})
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
                    
                    if status == 0: # Home error
                        print("Error while generating homepage")
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
    
if __name__ == "__main__":
    meower(debug = True, runAuth = True, autoAuth = False, ignoreUnauthedBlanks = False) # Runs the server
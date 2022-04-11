import json
import os

"""

Meower Files Module

This module provides filesystem functionality and a primitive JSON-file based database interface.
This file should be modified/refactored to interact with a JSON-friendly database server instead of filesystem directories and files.

"""

class Files:
    def __init__(self, logger, errorhandler):
        self.log = logger
        self.errorhandler = errorhandler
        
        # Get the directory of everything being stored in
        self.dirpath = "./Meower"
        
        # Create directories for Meower
        for directory in [
            # Root directories
            "./Meower/",
            "./Meower/Storage",
            "./Meower/Storage/Categories",
            
            # Home page directory
            "./Meower/Storage/Categories/Home",
            "./Meower/Storage/Categories/Home/Messages",
            "./Meower/Storage/Categories/Home/Indexes",
            
            # Announcements directory
            "./Meower/Storage/Categories/Announcements",
            "./Meower/Storage/Categories/Announcements/Messages",
            "./Meower/Storage/Categories/Announcements/Indexes",
            
            # Chats directory
            "./Meower/Storage/Chats",
            "./Meower/Storage/Chats/Messages",
            "./Meower/Storage/Chats/Indexes",
            "./Meower/Storage/Chats/UserIndexes",
           
            # User inbox directory
            "./Meower/Storage/Inboxes",
            "./Meower/Storage/Inboxes/Messages",
            "./Meower/Storage/Inboxes/Indexes",
            
            # Other directories
            "./Meower/Userdata",
            "./Meower/Logs",
            "./Meower/Config",
            "./Meower/Jail",
        ]:
            try:
                os.mkdir(directory)
            except FileExistsError:
                pass
        
        
        # Create server account file
        self.create_file("/Userdata/", "Server", {
                    "theme": "",
                    "mode": None,
                    "sfx": None,
                    "debug": None,
                    "bgm": None,
                    "bgm_song": None,
                    "layout": None,
                    "pfp_data": None,
                    "quote": None,
                    "email": None,
                    "pswd": None,
                    "lvl": None,
                    "banned": False
                }
            )
        
        # Create deleted account file
        self.create_file("/Userdata/", "Deleted", {
                    "theme": "",
                    "mode": None,
                    "sfx": None,
                    "debug": None,
                    "bgm": None,
                    "bgm_song": None,
                    "layout": None,
                    "pfp_data": None,
                    "quote": None,
                    "email": None,
                    "pswd": None,
                    "lvl": None,
                    "banned": False
                }
            )
        
        # Create IP banlist file
        self.create_file("/Jail/", "IPBanlist.json", {
            "wildcard": [
                "127.0.0.1",
            ],
            "users": {
                "Deleted": "127.0.0.1",
                "Server": "127.0.0.1",
            }
        })
        
        # Create Version support file
        self.create_file("/Config/", "supported_versions.json", {"index": ["scratch-beta-5-r3"]})
        
        # Create Trust Keys file
        self.create_file("/Config/", "trust_keys.json", {"index": ["meower"]})

        # Create Filter file
        self.create_file("/Config/", "filter.json", {"whitelist": [], "blacklist": []})
        
        self.log("Files initialized!")
    
    def create_directory(self, directory):
        try:
            os.mkdir(self.dirpath + directory)
            return True
        except FileExistsError:
            return True
        except Exception:
            self.log("{0}".format(self.errorhandler()))
            return False
    
    def create_file(self, directory, filename, contents):
        """
        Returns true if the file was created successfully.
        """
        try:
            if os.path.exists(self.dirpath + directory):
                if type(contents) == str:
                    f = open((self.dirpath + directory + filename), "x")
                    f.write(contents)
                    f.close()
                elif type(contents) == dict:
                    f = open((self.dirpath + directory + filename), "x")
                    f.write(json.dumps(contents))
                    f.close()
                else:
                    f = open((self.dirpath + directory + filename), "x")
                    f.write(str(contents))
                    f.close()
                return True
            else:
                return False
        except FileExistsError:
            return True
        except Exception:
            self.log("{0}".format(self.errorhandler()))
            return False
    
    def write_file(self, directory, filename, contents):
        """
        Returns true if the file was written successfully.
        """
        try:
            if os.path.exists(self.dirpath + directory):
                if type(contents) == str:
                    f = open((self.dirpath + directory + filename), "w")
                    f.write(contents)
                    f.close()
                elif type(contents) == dict:
                    f = open((self.dirpath + directory + filename), "w")
                    f.write(json.dumps(contents))
                    f.close()
                else:
                    f = open((self.dirpath + directory + filename), "w")
                    f.write(str(contents))
                    f.close()
                return True
            else:
                return False
        except:
            self.log("{0}".format(self.errorhandler()))
            return False
    
    def get_directory(self, directory):
        try:
            return True, os.listdir(self.dirpath + directory)
        except:
            self.log("{0}".format(self.errorhandler()))
            return False, None
    
    def load_file(self, filename):
        """
        Returns true (with a payload) if the file was read successfully.
        """
        try:
            if os.path.exists(self.dirpath + filename):
                payload = open(self.dirpath + filename).read()
                try: # Try to convert to JSON dict
                    payload = json.loads(payload)
                except:
                    self.log("Failed to parse JSON")
                return True, payload
            else:
                return False, None
        except:
            self.log("{0}".format(self.errorhandler()))
            return False, None

    def does_file_exist(self, directory, filename):
        """
        Returns true if the file exists.
        """
        if (type(directory) == str) and (type(filename) == str):
            try:
                result = os.listdir(self.dirpath + directory)
                return (filename in result)
            except:
                self.log("{0}".format(self.errorhandler()))
                return False
        else:
            self.log("Error on does_file_exist: Expected str for directory and filename, got {0} for directory and {1} for filename".format(type(directory), type(filename)))
            return False
    
    def delete_file(self, directory, filename):
        """
        Returns true if the file was deleted successfully.
        """
        try:
            if os.path.exists(self.dirpath + directory):
                os.remove(self.dirpath + directory + filename)
                return True
            else:
                return False
        except FileExistsError:
            return True
        except Exception:
            self.log("{0}".format(self.errorhandler()))
            return False

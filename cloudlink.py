#!/usr/bin/env python3

version = "0.1.7.6"

# Server based on https://github.com/Pithikos/python-websocket-server
# Client based on https://github.com/websocket-client/websocket-client

"""
CloudLink by MikeDEV
Please see https://github.com/MikeDev101/cloudlink for more details.
"""

import json
import sys
import threading
from typing import Any, Union, List, Dict
from websocket_server import WebsocketServer as ws_server
import websocket as ws_client
import time
import traceback
import sys

"""
Code formatting

(Type):(Code) | (Description)

Type: Letter
    I - Info
    E - Error

Code: Number, defines the code

Description: String, Describes the code
"""


def full_stack():
    exc = sys.exc_info()[0]
    if exc is not None:
        f = sys.exc_info()[-1].tb_frame.f_back  # type: ignore
        stack = traceback.extract_stack(f)
    else:
        stack = traceback.extract_stack()[:-1]
    trc = "Traceback (most recent call last):\n"
    stackstr = trc + "".join(traceback.format_list(stack))
    if exc is not None:
        stackstr += "  " + traceback.format_exc().lstrip(trc)
    return stackstr


def dummy(*args, **kwargs):
    pass


class CloudLink:
    def __init__(self, debug=False):  # Initializes CloudLink
        self.wss: ws_server = None  # type: ignore # Websocket Object
        self.userlist = []  # Stores usernames set on link
        self.callback_function = {  # For linking external code, use with functions
            "on_connect": dummy,  # Handles new connections (server) or when connected to a server (client)
            "on_error": dummy,  # Error reporter
            "on_packet": dummy,  # Packet handler
            "on_close": dummy,  # Runs code when disconnected (client) or server stops (server)
        }
        self.debug = debug  # Print back specific data
        self.statedata: dict = {}  # Place to store other garbage for modes
        self.codes = {  # Current set of CloudLink status/error self.codes
            "Test": "I:000 | Test",  # Test code
            "OK": "I:100 | OK",  # OK code
            "Syntax": "E:101 | Syntax",
            "Datatype": "E:102 | Datatype",
            "IDNotFound": "E:103 | ID not found",
            "InternalServerError": "E:104 | Internal",
            "Loop": "E:105 | Loop detected",
            "RateLimit": "E:106 | Too many requests",
            "TooLarge": "E:107 | Packet too large",
            "BrokenPipe": "E:108 | Broken pipe",
            "EmptyPacket": "E:109 | Empty packet",
            "IDConflict": "E:110 | ID conflict",
            "IDSet": "E:111 | ID already set",
            "TAEnabled": "I:112 | Trusted Access enabled",
            "TAInvalid": "E:113 | TA Key invalid",
            "TAExpired": "E:114 | TA Key expired",
            "Refused": "E:115 | Refused",
            "IDRequired": "E:116 | Username required",
            "TALostTrust": "E:117 | Trust lost",
            "Invalid": "E:118 | Invalid command",
            "Blocked": "E:119 | IP Blocked",
            "IPRequred": "E:120 | IP Address required",
            "TooManyUserNameChanges": "E:121 | Too Many Username Changes",
            "Disabled": "E:122 | Command disabled by sysadmin",
        }

        print("CloudLink v{0}".format(str(version)))  # Report version number
        if self.debug:
            print("Debug enabled")

    def server(
        self, ip="127.0.0.1", port=3000, threaded=False
    ):  # Runs CloudLink in server mode.
        try:
            # Change the link state to 1 (Server mode)
            self.wss = ws_server(host=ip, port=port)

            # Set the server's callbacks to CloudLink's class functions
            self.wss.set_fn_new_client(self._on_connection_server)
            self.wss.set_fn_client_left(self._closed_connection_server)
            self.wss.set_fn_message_received(self._on_packet_server)

            # Format dict for storing this mode's specific data

            if (not "motd" in self.statedata) or (not "motd_enable" in self.statedata):
                self.statedata["motd_enable"] = False
                self.statedata["motd"] = ""
            if (not "secure_enable" in self.statedata) or (
                not "secure_keys" in self.statedata
            ):
                self.statedata["secure_enable"] = False
                self.statedata["secure_keys"] = []
            if not "ip_blocklist" in self.statedata:
                self.statedata["ip_blocklist"] = set({""})

            self.statedata = {
                "ulist": {
                    "usernames": {},
                    "objs": {},
                },  # Username list for the "Usernames" block
                "secure_enable": False,  # Trusted Access enabler
                "secure_keys": [],  # Trusted Access keys
                "gmsg": "",  # Global data stream
                "motd_enable": self.statedata["motd_enable"],  # MOTD enabler
                "motd": self.statedata["motd"],  # MOTD text
                "secure_enable": self.statedata[
                    "secure_enable"
                ],  # Trusted Access enabler
                "secure_keys": self.statedata["secure_keys"],  # Trusted Access keys
                "trusted": [],  # Clients that are trusted with Secure Access, references memory objects only
                "ip_blocklist": self.statedata[
                    "ip_blocklist"
                ],  # Blocks clients with certain IP addresses
            }

            # Run the server
            print("Running server on ws://{0}:{1}/".format(ip, port))
            self.wss.run_forever(threaded=threaded)

        except Exception as e:
            if self.debug:
                print("Error at client: {0}".format(e))

    def stop(self, abrupt=False):  # Stops CloudLink (not sure if working)
        if self.wss is None:
            return  # Nothing to stop

        try:
            if abrupt:
                self.wss.shutdown_abruptly()
            else:
                self.wss.shutdown_gracefully()
        except Exception as e:
            if self.debug:
                print("Error at stop: {0}".format(e))

    def callback(
        self, callback_id, function
    ):  # Add user-friendly callbacks for CloudLink to be useful as a module
        if callback_id not in self.callback_function:
            raise Exception("Callback {0} does not exist!".format(callback_id))

        self.callback_function[callback_id] = function

    def trustedAccess(self, enable, keys):  # Enables secure access to the server.
        if not isinstance(enable, bool):
            raise TypeError("enable must be a boolean")

        if not isinstance(keys, list):
            keys = [keys]

        self.statedata["secure_enable"] = enable
        self.statedata["secure_keys"] = keys

    def sendPacket(
        self, msg
    ):  # User-friendly message sender for both server and client.
        if self.wss is None:
            raise Exception("CloudLink is not running!")

        try:
            if "id" not in msg:
                try:
                    if self.debug:
                        print('Sending "{0}" to all clients'.format(json.dumps(msg)))
                    self._send_to_all(msg)
                except Exception as e:
                    if self.debug:
                        print("Error on sendPacket (server): {0}".format(e))

                return

            if isinstance(msg["id"], list):
                clients = msg["id"]
            else:
                clients = [msg["id"]]

            del msg["id"]

            stringified_msg = json.dumps(msg)

            for client in clients:
                if isinstance(
                    client, dict
                ):  # Server is probably passing along the memory object for reference
                    if self.debug:
                        print(
                            "Info on sendPacket: Server passed along memory object:",
                            client["id"],
                            "will try to send packet directly",
                        )
                        print(
                            "Sending {0} to {1}".format(stringified_msg, client["id"])
                        )
                    try:
                        self.wss.send_message(client, stringified_msg)
                    except Exception as e:
                        if self.debug:
                            print("Error on sendPacket (server): {0}".format(e))
                elif isinstance(client, str) and (msg["cmd"] not in ["gmsg", "gvar"]):
                    if client not in self.statedata["ulist"]["usernames"]:
                        return

                    try:
                        for multisession in self.statedata["ulist"]["usernames"][
                            client
                        ]:
                            client = self.statedata["ulist"]["objs"][multisession][
                                "object"
                            ]
                            if self.debug:
                                print(
                                    "Sending {0} to {1}".format(stringified_msg, client)
                                )
                            self.wss.send_message(client, stringified_msg)
                    except Exception as e:
                        if self.debug:
                            print("Error on sendPacket (server): {0}".format(e))

        except Exception as e:
            print("Error at sendPacket: {0}".format(e))

    def setMOTD(self, motd, enable=True):  # Sets the MOTD on the server-side.
        if not isinstance(enable, bool):
            raise TypeError("enable must be a boolean")

        if not isinstance(motd, str):
            raise TypeError("motd must be a string")

        if enable:
            print('Set MOTD to "{0}".'.format(motd))
            self.statedata["motd"] = str(motd)
            self.statedata["motd_enable"] = True
        else:
            print("Disabled MOTD.")
            self.statedata["motd"] = None
            self.statedata["motd_enable"] = False

    def getUsernames(self) -> List[str]:  # Returns the username list.
        return list((self.statedata["ulist"]["usernames"]).keys())

    def getIPofUsername(
        self, user
    ):  # Allows the server to track user IPs for Trusted Access, uses the username of a client.
        if not self._get_obj_of_username(user) == None:
            return self._get_ip_of_obj(self._get_obj_of_username(user))
        return None

    def getIPofObject(
        self, obj
    ):  # Allows the server to track user IPs for Trusted Access, but uses the memory object of a client instead.
        return self._get_ip_of_obj(obj)

    def untrust(self, obj):
        if not self.statedata["secure_enable"]:
            if self.debug:
                print(
                    "Error: Cannot use the untrust function: Trusted Access not enabled!"
                )
            return

        if type(obj) == dict:
            if obj in self.statedata["trusted"]:
                self.statedata["trusted"].remove(obj)
                if self.debug:
                    print("Untrusted ID {0}.".format(obj["id"]))
            else:
                if self.debug:
                    print("Unable to untrust an ID that does not exist")

        elif type(obj) == str:
            obj = self._get_obj_of_username(obj)
            if obj is None:
                if self.debug:
                    print("Unable to untrust an ID that does not exist")
                return

            if obj not in self.statedata["trusted"]:
                if self.debug:
                    print("Unable to untrust an ID that does not exist")

            if isinstance(obj, list):
                if self.debug:
                    print("Error: Cannot untrust multiple usernames at once.")
                return

            self.statedata["trusted"].remove(obj)
            if self.debug:
                print("Untrusted ID {0}.".format(obj["id"]))

    def loadIPBlocklist(self, blist):  # Loads a list of IP addresses to block
        if not isinstance(blist, list):
            raise TypeError("blist must be a list")

        if "" not in blist:
            blist.append("")

        self.statedata["ip_blocklist"] = set(blist)
        if self.debug:
            print(
                "Loaded {0} blocked IPs into the blocklist!".format(
                    len(self.statedata["ip_blocklist"]) - 1
                )
            )

    def blockIP(self, ip):  # Blocks an IP address
        if not self.statedata["secure_enable"]:
            return

        if not isinstance(ip, str):
            raise TypeError("ip must be a string")

        if ip in self.statedata["ip_blocklist"]:
            return

        self.statedata["ip_blocklist"].add(ip)
        if self.debug:
            print("Blocked IP {0}!".format(ip))

    def unblockIP(self, ip):  # Unblocks an IP address
        if not self.statedata["secure_enable"]:
            return

        if not isinstance(ip, str):
            raise TypeError("ip must be a string")

        if not ip in self.statedata["ip_blocklist"]:
            return

        self.statedata["ip_blocklist"].remove(ip)
        if self.debug:
            print("Unblocked IP {0}!".format(ip))

    def getIPBlocklist(self):  # Returns the latest IP blocklist
        if not self.statedata["secure_enable"]:
            return []

        tmp = self.statedata["ip_blocklist"]
        tmp.remove("")
        return list(self.statedata["ip_blocklist"])

    def kickClient(
        self, obj
    ):  # Terminates a client's connection (should only be used for specific purposes)
        if not self.statedata["secure_enable"]:
            if self.debug:
                print(
                    "Error: Cannot use the kickClient function: Trusted Access not enabled!"
                )
            return

        if isinstance(obj, dict):
            if obj["id"] in self.statedata["ulist"]["objs"]:
                # Ask the WebsocketServer to terminate the connection
                obj["handler"].send_close(1000, bytes("", encoding="utf-8"))
                if self.debug:
                    print("Kicked ID {0}.".format(obj["id"]))
            else:
                if self.debug:
                    print("Unable to kick an ID that does not exist")

        elif isinstance(obj, str):
            obj = self._get_obj_of_username(obj)
            assert isinstance(obj, dict)

            if not obj == None:
                if obj["id"] in self.statedata["ulist"]["objs"]:
                    # Ask the WebsocketServer to terminate the connection
                    obj["handler"].send_close(1000, bytes("", encoding="utf-8"))
                    if self.debug:
                        print("Kicked ID {0}.".format(obj["id"]))
                else:
                    if self.debug:
                        print("Unable to kick an ID that does not exist")
            else:
                if self.debug:
                    print("Unable to kick an ID that does not exist")

    def _is_json(self, data):  # Checks if something is JSON
        if isinstance(data, dict):
            return True
        else:
            try:
                tmp = json.loads(data)
                return True
            except Exception as e:
                return False

    def _get_client_type(self, client):  # Gets client types to help prevent errors
        if client["id"] not in self.statedata["ulist"]["objs"]:
            return None

        self.statedata["ulist"]["objs"][client["id"]]["type"]

    def _get_obj_of_username(
        self, client
    ) -> Union[Dict[Any, Any], None, list]:  # Helps mitigate packet spoofing
        if client not in self.statedata["ulist"]["usernames"]:
            return None

        objects = list()
        for session in self.statedata["ulist"]["usernames"][client]:
            if session in self.statedata["ulist"]["objs"]:
                objects.append(self.statedata["ulist"]["objs"][session]["object"])
        return objects

    def _get_username_of_obj(self, obj):  # Returns the username of a client object
        if obj["id"] not in self.statedata["ulist"]["objs"]:
            return ""

        return self.statedata["ulist"]["objs"][obj["id"]]["username"]

    def _get_ip_of_obj(self, obj):  # Returns the IP address of a client object
        if not isinstance(obj, list):
            if obj["id"] in self.statedata["ulist"]["objs"]:
                return self.statedata["ulist"]["objs"][obj["id"]]["ip"]
            else:
                return ""

        ips = list()
        for session in obj:
            if session["id"] in self.statedata["ulist"]["objs"]:
                ips.append(self.statedata["ulist"]["objs"][session["id"]]["ip"])
        return ips

    def _is_obj_trusted(self, obj):  # Checks if a client is trusted on the link
        if not self.statedata["secure_enable"]:
            return False

        return (obj in self.statedata["trusted"]) and (not self._is_obj_blocked(obj))

    def _is_obj_blocked(self, obj):  # Checks if a client is IP blocked
        if not self.statedata["secure_enable"]:
            return False

        return self._get_ip_of_obj(obj) in self.statedata["ip_blocklist"]

    def _send_to_all(self, payload):  # "Better" (?) send to all function
        if self.wss is None:
            return

        tmp_payload = payload
        for client in self.wss.clients:
            # print("sending {0} to {1}".format(payload, client["id"]))
            if self._get_client_type(client) == "scratch":
                # print("sending to all, {0} is a scratcher".format(client["id"]))
                if ("val" in payload) and (type(payload["val"]) == dict):
                    # print("stringifying nested json")
                    tmp_payload["val"] = json.dumps(payload["val"])
                if not self.statedata["secure_enable"]:
                    self.wss.send_message(client, json.dumps(tmp_payload))
                else:
                    if self._is_obj_trusted(client):
                        self.wss.send_message(client, json.dumps(tmp_payload))
            else:
                if not self.statedata["secure_enable"]:
                    self.wss.send_message(client, json.dumps(payload))
                else:
                    if self._is_obj_trusted(client):
                        self.wss.send_message(client, json.dumps(payload))

    def _server_packet_handler(
        self, client, server, message, listener_detected=False, listener_id=""
    ):  # The almighty packet handler, single-handedly responsible for over hundreds of lines of code
        if self.wss is None:
            return

        if client is None:
            return

        if len(str(message)) == 0:
            if self.debug:
                print("Error: Packet is empty")
            if listener_detected:
                self.wss.send_message(
                    client,
                    json.dumps(
                        {
                            "cmd": "statuscode",
                            "val": self.codes["EmptyPacket"],
                            "listener": listener_id,
                        }
                    ),
                )
            else:
                self.wss.send_message(
                    client,
                    json.dumps({"cmd": "statuscode", "val": self.codes["EmptyPacket"]}),
                )

        try:
            msg = json.loads(message)

            if (
                type(msg["id"]) != str
                or type(msg["id"]) == dict
                or type(msg["id"]) == list
            ):
                msg["id"] = str(msg["id"])
            else:
                if self.debug:
                    print(
                        'Error: Packet "id" datatype invalid: expecting <class "str">, got {0}'.format(
                            type(msg["id"])
                        )
                    )

                self.wss.send_message(
                    client,
                    json.dumps(
                        {
                            "cmd": "statuscode",
                            "val": self.codes["Datatype"],
                            "listener": listener_id,
                        }
                        if listener_detected
                        else {"cmd": "statuscode", "val": self.codes["Datatype"]}
                    ),
                )
                return

        except json.decoder.JSONDecodeError:
            if self.debug:
                print("Error: Failed to parse JSON")
            return self.wss.send_message(
                client,
                json.dumps(
                    {
                        "cmd": "statuscode",
                        "val": self.codes["Syntax"],
                        "listener": listener_id,
                    }
                ),
            )
        except Exception as e:
            if self.debug:
                print(f"Error on _server_packet_handler: {full_stack()}")
            self.wss.send_message(
                client,
                json.dumps(
                    {
                        "cmd": "statuscode",
                        "val": self.codes["InternalServerError"],
                        "listener": listener_id,
                    }
                ),
            )
            return

        if "cmd" in msg:
            # Verify that the packet contains the command parameter, which is needed to work.
            if isinstance(msg["cmd"], str):
                if msg["cmd"] in [
                    "gmsg",
                    "pmsg",
                    "setid",
                    "direct",
                    "gvar",
                    "pvar",
                    "ping",
                ]:
                    self.handle_commands(client, msg, listener_detected, listener_id)
                else:
                    # Route the packet using UPL.
                    self.handle_upl(client, msg, listener_detected, listener_id)
            else:
                if self.debug:
                    print(
                        f'Error: Packet "cmd" datatype invalid: expecting <class "bool">, got {type(msg["cmd"])}'
                    )
                self.wss.send_message(
                    client,
                    json.dumps(
                        {
                            "cmd": "statuscode",
                            "val": self.codes["Datatype"],
                            "listener": listener_id,
                        }
                    ),
                )
        else:
            if self.debug:
                print('Error: Packet missing "cmd" parameter')
            self.wss.send_message(
                client,
                json.dumps(
                    {
                        "cmd": "statuscode",
                        "val": self.codes["Syntax"],
                        "listener": listener_id,
                    }
                ),
            )

    def handle_upl(self, client, msg, listener_detected=False, listener_id=""):
        if self.wss is None:
            return
        if ("val" in msg) and (
            "id" in msg
        ):  # Verify that the packet contains the required parameters.
            if self._get_client_type(client) == "scratch":
                if self._is_json(msg["val"]):
                    msg["val"] = json.loads(msg["val"])
            if msg["id"] in self.statedata["ulist"]["usernames"]:
                if True:
                    if not client == self._get_obj_of_username(msg["id"]):
                        try:
                            otherclient = self._get_obj_of_username(msg["id"])
                            if not len(self._get_username_of_obj(client)) == 0:
                                msg["origin"] = self._get_username_of_obj(client)
                                if (
                                    self._get_client_type(otherclient) == "scratch"
                                ) and (
                                    (self._is_json(msg["val"]))
                                    or (type(msg["val"]) == dict)
                                ):
                                    tmp_val = json.dumps(msg["val"])
                                else:
                                    tmp_val = msg["val"]

                                if self.debug:
                                    print("Routing {0} to {1}".format(msg, msg["id"]))
                                del msg["id"]
                                self.wss.send_message(otherclient, json.dumps(msg))

                                if listener_detected:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["OK"],
                                                "listener": listener_id,
                                            }
                                        ),
                                    )
                                else:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["OK"],
                                            }
                                        ),
                                    )
                            else:
                                if listener_detected:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["IDRequired"],
                                                "listener": listener_id,
                                            }
                                        ),
                                    )
                                else:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["IDRequired"],
                                            }
                                        ),
                                    )
                        except Exception as e:
                            if self.debug:
                                print("Error on _server_packet_handler: {0}".format(e))
                            if listener_detected:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["InternalServerError"],
                                            "listener": listener_id,
                                        }
                                    ),
                                )
                            else:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["InternalServerError"],
                                        }
                                    ),
                                )
                    else:
                        if self.debug:
                            print("Error: Potential packet loop detected, aborting")
                        if listener_detected:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {
                                        "cmd": "statuscode",
                                        "val": self.codes["Loop"],
                                        "listener": listener_id,
                                    }
                                ),
                            )
                        else:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {"cmd": "statuscode", "val": self.codes["Loop"]}
                                ),
                            )
                else:
                    if self.debug:
                        print("Error: Packet too large")
                    if listener_detected:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {
                                    "cmd": "statuscode",
                                    "val": self.codes["TooLarge"],
                                    "listener": listener_id,
                                }
                            ),
                        )
                    else:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {"cmd": "statuscode", "val": self.codes["TooLarge"]}
                            ),
                        )
            else:
                if self.debug:
                    print("Error: ID Not found")
                if listener_detected:
                    self.wss.send_message(
                        client,
                        json.dumps(
                            {
                                "cmd": "statuscode",
                                "val": self.codes["IDNotFound"],
                                "listener": listener_id,
                            }
                        ),
                    )
                else:
                    self.wss.send_message(
                        client,
                        json.dumps(
                            {"cmd": "statuscode", "val": self.codes["IDNotFound"]}
                        ),
                    )
        else:
            if self.debug:
                print("Error: Packet missing parameters")
            if listener_detected:
                self.wss.send_message(
                    client,
                    json.dumps(
                        {
                            "cmd": "statuscode",
                            "val": self.codes["Syntax"],
                            "listener": listener_id,
                        }
                    ),
                )
            else:
                self.wss.send_message(
                    client,
                    json.dumps({"cmd": "statuscode", "val": self.codes["Syntax"]}),
                )

    def handle_commands(self, client, msg, listener_detected=False, listener_id=""):
        if self.wss is None:
            return
        if msg["cmd"] == "gmsg":  # Handles global messages.
            if False:
                if (
                    "val" in msg
                ):  # Verify that the packet contains the required parameters.
                    if self._get_client_type(client) == "scratch":
                        if self._is_json(msg["val"]):
                            msg["val"] = json.loads(msg["val"])
                    if True:
                        if self.debug:
                            print("message is {0} bytes".format(len(str(msg["val"]))))
                        self.statedata["gmsg"] = msg["val"]
                        # Send the packet to all clients.
                        self._send_to_all({"cmd": "gmsg", "val": msg["val"]})
                        if listener_detected:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {
                                        "cmd": "statuscode",
                                        "val": self.codes["OK"],
                                        "listener": listener_id,
                                    }
                                ),
                            )
                        else:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {"cmd": "statuscode", "val": self.codes["OK"]}
                                ),
                            )
                    else:
                        if self.debug:
                            print("Error: Packet too large")
                        if listener_detected:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {
                                        "cmd": "statuscode",
                                        "val": self.codes["TooLarge"],
                                        "listener": listener_id,
                                    }
                                ),
                            )
                        else:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {"cmd": "statuscode", "val": self.codes["TooLarge"]}
                                ),
                            )
                else:
                    if self.debug:
                        print("Error: Packet missing parameters")
                    if listener_detected:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {
                                    "cmd": "statuscode",
                                    "val": self.codes["Syntax"],
                                    "listener": listener_id,
                                }
                            ),
                        )
                    else:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {"cmd": "statuscode", "val": self.codes["Syntax"]}
                            ),
                        )
            else:
                self.wss.send_message(
                    client,
                    json.dumps({"cmd": "statuscode", "val": self.codes["Disabled"]}),
                )

        if msg["cmd"] == "pmsg":  # Handles private messages.
            if ("val" in msg) and (
                "id" in msg
            ):  # Verify that the packet contains the required parameters.
                if self._get_client_type(client) == "scratch":
                    if self._is_json(msg["val"]):
                        msg["val"] = json.loads(msg["val"])
                if msg["id"] in self.statedata["ulist"]["usernames"]:
                    if True:
                        if not client == self._get_obj_of_username(msg["id"]):
                            try:
                                for otherclient in self._get_obj_of_username(msg["id"]):  # type: ignore
                                    if not len(self._get_username_of_obj(client)) == 0:
                                        msg["origin"] = self._get_username_of_obj(
                                            client
                                        )
                                        if (
                                            self._get_client_type(otherclient)
                                            == "scratch"
                                        ) and (self._is_json(msg["val"])):
                                            tmp_val = json.dumps(msg["val"])
                                        else:
                                            tmp_val = msg["val"]

                                        if self.debug:
                                            print(
                                                "Sending {0} to {1}".format(
                                                    msg, msg["id"]
                                                )
                                            )
                                        del msg["id"]
                                        self.wss.send_message(
                                            otherclient,
                                            json.dumps(
                                                {
                                                    "cmd": "pmsg",
                                                    "val": tmp_val,
                                                    "origin": msg["origin"],
                                                }
                                            ),
                                        )
                                        if listener_detected:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["OK"],
                                                        "listener": listener_id,
                                                    }
                                                ),
                                            )
                                        else:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["OK"],
                                                    }
                                                ),
                                            )
                                    else:
                                        if listener_detected:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["IDRequired"],
                                                        "listener": listener_id,
                                                    }
                                                ),
                                            )
                                        else:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["IDRequired"],
                                                    }
                                                ),
                                            )
                            except Exception as e:
                                if self.debug:
                                    print(
                                        "Error on _server_packet_handler: {0}".format(e)
                                    )
                                    if listener_detected:
                                        self.wss.send_message(
                                            client,
                                            json.dumps(
                                                {
                                                    "cmd": "statuscode",
                                                    "val": self.codes[
                                                        "InternalServerError"
                                                    ],
                                                    "listener": listener_id,
                                                }
                                            ),
                                        )
                                    else:
                                        self.wss.send_message(
                                            client,
                                            json.dumps(
                                                {
                                                    "cmd": "statuscode",
                                                    "val": self.codes[
                                                        "InternalServerError"
                                                    ],
                                                }
                                            ),
                                        )
                        else:
                            if self.debug:
                                print("Error: Potential packet loop detected, aborting")
                            if listener_detected:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["Loop"],
                                            "listener": listener_id,
                                        }
                                    ),
                                )
                            else:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {"cmd": "statuscode", "val": self.codes["Loop"]}
                                    ),
                                )
                    else:
                        if self.debug:
                            print("Error: Packet too large")
                        if listener_detected:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {
                                        "cmd": "statuscode",
                                        "val": self.codes["TooLarge"],
                                        "listener": listener_id,
                                    }
                                ),
                            )
                        else:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {"cmd": "statuscode", "val": self.codes["TooLarge"]}
                                ),
                            )
                else:
                    if self.debug:
                        print("Error: ID Not found")
                    if listener_detected:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {
                                    "cmd": "statuscode",
                                    "val": self.codes["IDNotFound"],
                                    "listener": listener_id,
                                }
                            ),
                        )
                    else:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {"cmd": "statuscode", "val": self.codes["IDNotFound"]}
                            ),
                        )
            else:
                if self.debug:
                    print("Error: Packet missing parameters")
                if listener_detected:
                    self.wss.send_message(
                        client,
                        json.dumps(
                            {
                                "cmd": "statuscode",
                                "val": self.codes["Syntax"],
                                "listener": listener_id,
                            }
                        ),
                    )
                else:
                    self.wss.send_message(
                        client,
                        json.dumps({"cmd": "statuscode", "val": self.codes["Syntax"]}),
                    )

        if msg["cmd"] == "setid":  # Sets the username of the client.
            if False:
                if (
                    "val" in msg
                ):  # Verify that the packet contains the required parameters.
                    if not len(str(msg["val"])) == 0:
                        if True:
                            if type(msg["val"]) == str:
                                if (
                                    self.statedata["ulist"]["objs"][client["id"]][
                                        "username"
                                    ]
                                    == ""
                                ):
                                    if (
                                        not msg["val"]
                                        in self.statedata["ulist"]["usernames"]
                                    ):
                                        # Add the username to the list
                                        self.statedata["ulist"]["usernames"][
                                            msg["val"]
                                        ] = client["id"]
                                        # Set the object's username info
                                        self.statedata["ulist"]["objs"][client["id"]][
                                            "username"
                                        ] = msg["val"]

                                        if listener_detected:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["OK"],
                                                        "listener": listener_id,
                                                    }
                                                ),
                                            )
                                        else:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["OK"],
                                                    }
                                                ),
                                            )
                                        self._send_to_all(
                                            {"cmd": "ulist", "val": self._get_ulist()}
                                        )
                                        if self.debug:
                                            print(
                                                "User {0} set username: {1}".format(
                                                    client["id"], msg["val"]
                                                )
                                            )
                                    else:
                                        if self.debug:
                                            print(
                                                "Error: Refusing to set username because it would cause a conflict"
                                            )
                                        if listener_detected:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["IDConflict"],
                                                        "listener": listener_id,
                                                    }
                                                ),
                                            )
                                        else:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["IDConflict"],
                                                    }
                                                ),
                                            )
                                else:
                                    if self.debug:
                                        print(
                                            "Error: Refusing to set username because username has already been set"
                                        )
                                    if listener_detected:
                                        self.wss.send_message(
                                            client,
                                            json.dumps(
                                                {
                                                    "cmd": "statuscode",
                                                    "val": self.codes["IDSet"],
                                                    "listener": listener_id,
                                                }
                                            ),
                                        )
                                    else:
                                        self.wss.send_message(
                                            client,
                                            json.dumps(
                                                {
                                                    "cmd": "statuscode",
                                                    "val": self.codes["IDSet"],
                                                }
                                            ),
                                        )
                            else:
                                if self.debug:
                                    print(
                                        'Error: Packet "val" datatype invalid: expecting <class "str">, got {0}'.format(
                                            type(msg["cmd"])
                                        )
                                    )
                                if listener_detected:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["Datatype"],
                                                "listener": listener_id,
                                            }
                                        ),
                                    )
                                else:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["Datatype"],
                                            }
                                        ),
                                    )
                        else:
                            if self.debug:
                                print("Error: Packet too large")
                            if listener_detected:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["TooLarge"],
                                            "listener": listener_id,
                                        }
                                    ),
                                )
                            else:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["TooLarge"],
                                        }
                                    ),
                                )
                    else:
                        if self.debug:
                            print("Error: Packet is empty")
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {"cmd": "statuscode", "val": self.codes["EmptyPacket"]}
                            ),
                        )
                else:
                    if self.debug:
                        print("Error: Packet missing parameters")
                    self.wss.send_message(
                        client,
                        json.dumps({"cmd": "statuscode", "val": self.codes["Syntax"]}),
                    )
            else:
                self.wss.send_message(
                    client,
                    json.dumps({"cmd": "statuscode", "val": self.codes["Disabled"]}),
                )

        if msg["cmd"] == "direct":  # Direct packet handler for server.
            if self._get_client_type(client) == "scratch":
                if "val" in msg:
                    if (self._is_json(msg["val"])) and (type(msg["val"]) == str):
                        try:
                            msg["val"] = json.loads(msg["val"])
                        except json.decoder.JSONDecodeError:
                            if self.debug:
                                print("Failed to decode JSON of direct's nested data")
                            if listener_detected:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["Syntax"],
                                            "listener": listener_id,
                                        }
                                    ),
                                )
                            else:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["Syntax"],
                                        }
                                    ),
                                )
                            return

            if "val" in msg:
                if not self.callback_function["on_packet"] == None:
                    if "cmd" in msg["val"]:
                        if msg["val"]["cmd"] == "type":
                            if "val" in msg["val"]:
                                if (
                                    self.statedata["ulist"]["objs"][client["id"]][
                                        "type"
                                    ]
                                    == None
                                ):  # Prevent the client from changing types
                                    self.statedata["ulist"]["objs"][client["id"]][
                                        "type"
                                    ] = msg["val"][
                                        "val"
                                    ]  # Set the client type
                                    if self.debug:
                                        if msg["val"]["val"] == "scratch":
                                            print(
                                                "Client {0} is scratch type".format(
                                                    client["id"]
                                                )
                                            )
                                        elif msg["val"]["val"] == "py":
                                            print(
                                                "Client {0} is python type".format(
                                                    client["id"]
                                                )
                                            )
                                        elif msg["val"]["val"] == "js":
                                            print(
                                                "Client {0} is js type".format(
                                                    client["id"]
                                                )
                                            )
                                        else:
                                            print(
                                                "Client {0} is of unknown client type, claims it's {1}".format(
                                                    client["id"], (msg["val"]["val"])
                                                )
                                            )
                                    # self.wss.send_message(client, json.dumps({"cmd": "statuscode", "val": self.codes["OK"]}))
                            else:
                                if self.debug:
                                    print("Error: Packet missing parameters")
                                if listener_detected:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["Syntax"],
                                                "listener": listener_id,
                                            }
                                        ),
                                    )
                                else:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["Syntax"],
                                            }
                                        ),
                                    )

                        else:
                            if "val" in msg["val"]:
                                if len(self._get_username_of_obj(client)) == 0:
                                    origin = client
                                    if self.debug:
                                        print(
                                            "Handling direct custom command from {0}".format(
                                                origin["id"]
                                            )
                                        )
                                else:
                                    origin = self._get_username_of_obj(client)
                                    if self.debug:
                                        print(
                                            "Handling direct custom command from {0}".format(
                                                origin
                                            )
                                        )

                                if listener_detected:
                                    self.callback_function["on_packet"](
                                        {
                                            "cmd": msg["val"]["cmd"],
                                            "val": msg["val"]["val"],
                                            "id": origin,
                                            "listener": listener_id,
                                        }
                                    )
                                else:
                                    self.callback_function["on_packet"](
                                        {
                                            "cmd": msg["val"]["cmd"],
                                            "val": msg["val"]["val"],
                                            "id": origin,
                                        }
                                    )
                            else:
                                if self.debug:
                                    print("Error: Packet missing parameters")
                                if listener_detected:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["Syntax"],
                                                "listener": listener_id,
                                            }
                                        ),
                                    )
                                else:
                                    self.wss.send_message(
                                        client,
                                        json.dumps(
                                            {
                                                "cmd": "statuscode",
                                                "val": self.codes["Syntax"],
                                            }
                                        ),
                                    )
                    else:
                        if len(self._get_username_of_obj(client)) == 0:
                            origin = client
                            if self.debug:
                                print(
                                    "Handling direct command from {0}".format(
                                        origin["id"]
                                    )
                                )
                        else:
                            origin = self._get_username_of_obj(client)
                            if self.debug:
                                print("Handling direct command from {0}".format(origin))
                        if listener_detected:
                            self.callback_function["on_packet"](
                                {
                                    "val": msg["val"],
                                    "id": origin,
                                    "listener": listener_id,
                                }
                            )
                        else:
                            self.callback_function["on_packet"](
                                {"val": msg["val"], "id": origin}
                            )
            else:
                if self.debug:
                    print("Error: Packet missing parameters")
                if listener_detected:
                    self.wss.send_message(
                        client,
                        json.dumps(
                            {
                                "cmd": "statuscode",
                                "val": self.codes["Syntax"],
                                "listener": listener_id,
                            }
                        ),
                    )
                else:
                    self.wss.send_message(
                        client,
                        json.dumps({"cmd": "statuscode", "val": self.codes["Syntax"]}),
                    )

        if msg["cmd"] == "gvar":  # Handles global variables.
            if False:
                if ("val" in msg) and (
                    "name" in msg
                ):  # Verify that the packet contains the required parameters.
                    if self._get_client_type(client) == "scratch":
                        if self._is_json(msg["val"]):
                            msg["val"] = json.loads(msg["val"])
                    if not len(str(msg["name"])) > 100:
                        # Send the packet to all clients.
                        self._send_to_all(
                            {"cmd": "gvar", "val": msg["val"], "name": msg["name"]}
                        )

                        if listener_detected:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {
                                        "cmd": "statuscode",
                                        "val": self.codes["OK"],
                                        "listener": listener_id,
                                    }
                                ),
                            )
                        else:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {"cmd": "statuscode", "val": self.codes["OK"]}
                                ),
                            )
                    else:
                        if self.debug:
                            print("Error: Packet too large")
                        if listener_detected:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {
                                        "cmd": "statuscode",
                                        "val": self.codes["TooLarge"],
                                        "listener": listener_id,
                                    }
                                ),
                            )
                        else:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {"cmd": "statuscode", "val": self.codes["TooLarge"]}
                                ),
                            )
                else:
                    if self.debug:
                        print("Error: Packet missing parameters")
                    if listener_detected:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {
                                    "cmd": "statuscode",
                                    "val": self.codes["Syntax"],
                                    "listener": listener_id,
                                }
                            ),
                        )
                    else:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {"cmd": "statuscode", "val": self.codes["Syntax"]}
                            ),
                        )
            else:
                self.wss.send_message(
                    client,
                    json.dumps({"cmd": "statuscode", "val": self.codes["Disabled"]}),
                )

        if msg["cmd"] == "pvar":  # Handles private variables.
            if (
                ("val" in msg) and ("id" in msg) and ("name" in msg)
            ):  # Verify that the packet contains the required parameters.
                if self._get_client_type(client) == "scratch":
                    if self._is_json(msg["val"]):
                        msg["val"] = json.loads(msg["val"])
                if msg["id"] in self.statedata["ulist"]["usernames"]:
                    if not len(str(msg["name"])) > 1000:
                        if not client == self._get_obj_of_username(msg["id"]):
                            try:
                                for otherclient in self._get_obj_of_username(msg["id"]):
                                    if not len(self._get_username_of_obj(client)) == 0:
                                        msg["origin"] = self._get_username_of_obj(
                                            client
                                        )
                                        if (
                                            self._get_client_type(otherclient)
                                            == "scratch"
                                        ) and (
                                            (self._is_json(msg["val"]))
                                            or (type(msg["val"]) == dict)
                                        ):
                                            tmp_val = json.dumps(msg["val"])
                                        else:
                                            tmp_val = msg["val"]
                                        if self.debug:
                                            print(
                                                "Sending {0} to {1}".format(
                                                    msg, msg["id"]
                                                )
                                            )
                                        del msg["id"]
                                        self.wss.send_message(
                                            otherclient,
                                            json.dumps(
                                                {
                                                    "cmd": "pvar",
                                                    "val": tmp_val,
                                                    "name": msg["name"],
                                                    "origin": msg["origin"],
                                                }
                                            ),
                                        )
                                        if listener_detected:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["OK"],
                                                        "listener": listener_id,
                                                    }
                                                ),
                                            )
                                        else:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["OK"],
                                                    }
                                                ),
                                            )
                                    else:
                                        if listener_detected:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["IDRequired"],
                                                        "listener": listener_id,
                                                    }
                                                ),
                                            )
                                        else:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["IDRequired"],
                                                    }
                                                ),
                                            )
                            except Exception as e:
                                if self.debug:
                                    print(
                                        "Error on _server_packet_handler: {0}".format(e)
                                    )
                                    if listener_detected:
                                        self.wss.send_message(
                                            client,
                                            json.dumps(
                                                {
                                                    "cmd": "statuscode",
                                                    "val": self.codes[
                                                        "InternalServerError"
                                                    ],
                                                    "listener": listener_id,
                                                }
                                            ),
                                        )
                                    else:
                                        self.wss.send_message(
                                            client,
                                            json.dumps(
                                                {
                                                    "cmd": "statuscode",
                                                    "val": self.codes[
                                                        "InternalServerError"
                                                    ],
                                                }
                                            ),
                                        )
                        else:
                            if self.debug:
                                print("Error: Potential packet loop detected, aborting")
                            if listener_detected:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["Loop"],
                                            "listener": listener_id,
                                        }
                                    ),
                                )
                            else:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {"cmd": "statuscode", "val": self.codes["Loop"]}
                                    ),
                                )
                    else:
                        if self.debug:
                            print("Error: Packet too large")
                        if listener_detected:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {
                                        "cmd": "statuscode",
                                        "val": self.codes["TooLarge"],
                                        "listener": listener_id,
                                    }
                                ),
                            )
                        else:
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {"cmd": "statuscode", "val": self.codes["TooLarge"]}
                                ),
                            )
                else:
                    if self.debug:
                        print("Error: ID Not found")
                    if listener_detected:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {
                                    "cmd": "statuscode",
                                    "val": self.codes["IDNotFound"],
                                    "listener": listener_id,
                                }
                            ),
                        )
                    else:
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {"cmd": "statuscode", "val": self.codes["IDNotFound"]}
                            ),
                        )
            else:
                if self.debug:
                    print("Error: Packet missing parameters")
                if listener_detected:
                    self.wss.send_message(
                        client,
                        json.dumps(
                            {
                                "cmd": "statuscode",
                                "val": self.codes["Syntax"],
                                "listener": listener_id,
                            }
                        ),
                    )
                else:
                    self.wss.send_message(
                        client,
                        json.dumps({"cmd": "statuscode", "val": self.codes["Syntax"]}),
                    )

        if msg["cmd"] == "ping":
            if self.debug:
                print("Ping from client {0}".format(client["id"]))
            if listener_detected:
                self.wss.send_message(
                    client,
                    json.dumps(
                        {
                            "cmd": "ping",
                            "val": self.codes["OK"],
                            "listener": listener_id,
                        }
                    ),
                )
            else:
                self.wss.send_message(
                    client, json.dumps({"cmd": "ping", "val": self.codes["OK"]})
                )

    def _get_ulist(self):  # Generates username list
        tmp_ulist = list((self.statedata["ulist"]["usernames"]).keys())
        for item in tmp_ulist:
            if item[0] == "%" and item[len(item) - 1] == "%":
                tmp_ulist.pop(tmp_ulist.index(item))

        output = ""
        for item in tmp_ulist:
            output = output + item + ";"
        return output

    def _on_connection_server(
        self, client, server
    ):  # Server-side new connection handler
        if self.wss is None:
            return

        if client is None:
            return

        try:
            if self.debug:
                print("New connection: {0}".format(str(client["id"])))

            # Add the client to the ulist object in memory.
            self.statedata["ulist"]["objs"][client["id"]] = {
                "object": client,
                "username": "",
                "ip": client["handler"].ip,
                "type": None,
            }

            # Send the MOTD if enabled.
            if self.statedata["motd_enable"]:
                self.wss.send_message(
                    client,
                    json.dumps(
                        {
                            "cmd": "direct",
                            "val": {"cmd": "motd", "val": str(self.statedata["motd"])},
                        }
                    ),
                )

            # Send server version.
            self.wss.send_message(
                client,
                json.dumps(
                    {"cmd": "direct", "val": {"cmd": "vers", "val": str(version)}}
                ),
            )

            if not self.statedata["secure_enable"]:
                # Send the current username list.
                self.wss.send_message(
                    client, json.dumps({"cmd": "ulist", "val": self._get_ulist()})
                )

                # Send the current global data stream value.
                self.wss.send_message(
                    client,
                    json.dumps({"cmd": "gmsg", "val": str(self.statedata["gmsg"])}),
                )
            else:
                # Tell the client that the server is expecting a Trusted Access key.
                self.wss.send_message(
                    client,
                    json.dumps({"cmd": "statuscode", "val": self.codes["TAEnabled"]}),
                )

            if not self.callback_function["on_connect"] == None:

                def run(*args):
                    if self.wss is None:
                        return

                    try:
                        self.callback_function["on_connect"](client)
                    except Exception as e:
                        if self.debug:
                            print("Error on _on_connection_server: {0}".format(e))
                        self.wss.send_message(
                            client,
                            json.dumps(
                                {
                                    "cmd": "statuscode",
                                    "val": self.codes["InternalServerError"],
                                }
                            ),
                        )

                threading.Thread(target=run).start()
        except Exception as e:
            if self.debug:
                print("Error on _on_connection_server: {0}".format(e))
            self.wss.send_message(
                client,
                json.dumps(
                    {"cmd": "statuscode", "val": self.codes["InternalServerError"]}
                ),
            )

    def _closed_connection_server(
        self, client, server
    ):  # Server-side client closed connection handler
        if not type(client) == type(None):
            try:
                if self.debug:
                    if client["id"] in self.statedata["ulist"]["objs"]:
                        if (
                            self.statedata["ulist"]["objs"][client["id"]]["username"]
                            == ""
                        ):
                            print("Connection closed: {0}".format(str(client["id"])))
                        else:
                            print(
                                "Connection closed: {0} ({1})".format(
                                    str(client["id"]),
                                    str(
                                        self.statedata["ulist"]["objs"][client["id"]][
                                            "username"
                                        ]
                                    ),
                                )
                            )
                    else:
                        print("Connection closed: {0}".format(str(client["id"])))

                if not self.callback_function["on_close"] == None:
                    try:
                        self.callback_function["on_close"](client)
                    except Exception as e:
                        if self.debug:
                            print("Error on _closed_connection_server: {0}".format(e))

                # Remove entries from username list and userlist objects
                if client["id"] in self.statedata["ulist"]["objs"]:
                    username = self.statedata["ulist"]["objs"][client["id"]]["username"]
                    if username in self.statedata["ulist"]["usernames"]:
                        # multisession handling
                        if (
                            client["id"]
                            in self.statedata["ulist"]["usernames"][username]
                        ):
                            self.statedata["ulist"]["usernames"][username].remove(
                                client["id"]
                            )
                        if len(self.statedata["ulist"]["usernames"][username]) == 0:
                            del self.statedata["ulist"]["usernames"][username]

                    del self.statedata["ulist"]["objs"][client["id"]]

                if self.statedata["secure_enable"]:
                    if client in self.statedata["trusted"]:
                        self.statedata["trusted"].remove(client)

                self._send_to_all({"cmd": "ulist", "val": self._get_ulist()})
            except Exception as e:
                if self.debug:
                    print("Error on _closed_connection_server: {0}".format(e))

    def _on_packet_server(
        self, client, server, message
    ):  # Server-side new packet handler (Gives it's powers to _server_packet_handler)
        if self.wss is None:
            return
        if not type(client) == type(None):
            try:
                if self.debug:
                    print(
                        "New packet from {0}: {1} bytes".format(
                            str(client["id"]), str(len(message))
                        )
                    )
                if self.statedata["secure_enable"]:
                    if not self._is_obj_trusted(client):
                        try:
                            msg = json.loads(message)
                            listener_detected = ("listener" in msg) and (
                                type(msg["listener"]) == str
                            )
                            listener_id = ""
                            # Support listener IDs feature from CL Turbo
                            if listener_detected:
                                listener_id = msg["listener"]

                            if ("cmd" in msg) and ("val" in msg):
                                if (
                                    (msg["cmd"] == "direct")
                                    and (type(msg["val"]) == dict)
                                    and (msg["val"]["cmd"] in ["ip", "type"])
                                ):
                                    if self._is_obj_blocked(client):
                                        if self.debug:
                                            print(
                                                "User {0} is IP blocked, not trusting".format(
                                                    client["id"]
                                                )
                                            )
                                        # Tell the client it is IP blocked
                                        if listener_detected:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["Blocked"],
                                                        "listener": listener_id,
                                                    }
                                                ),
                                            )
                                        else:
                                            self.wss.send_message(
                                                client,
                                                json.dumps(
                                                    {
                                                        "cmd": "statuscode",
                                                        "val": self.codes["Blocked"],
                                                    }
                                                ),
                                            )
                                    else:
                                        self._server_packet_handler(
                                            client,
                                            server,
                                            message,
                                            listener_detected,
                                            listener_id,
                                        )
                                else:
                                    if (msg["cmd"] == "direct") or (
                                        msg["cmd"] == "gmsg"
                                    ):
                                        if self._is_obj_blocked(client):
                                            if self.debug:
                                                print(
                                                    "User {0} is IP blocked, not trusting".format(
                                                        client["id"]
                                                    )
                                                )
                                            # Tell the client it is IP blocked
                                            if listener_detected:
                                                self.wss.send_message(
                                                    client,
                                                    json.dumps(
                                                        {
                                                            "cmd": "statuscode",
                                                            "val": self.codes[
                                                                "Blocked"
                                                            ],
                                                            "listener": listener_id,
                                                        }
                                                    ),
                                                )
                                            else:
                                                self.wss.send_message(
                                                    client,
                                                    json.dumps(
                                                        {
                                                            "cmd": "statuscode",
                                                            "val": self.codes[
                                                                "Blocked"
                                                            ],
                                                        }
                                                    ),
                                                )
                                        else:
                                            if type(msg["val"]) == str:
                                                if (
                                                    msg["val"]
                                                    in self.statedata["secure_keys"]
                                                ):
                                                    if (
                                                        self._get_ip_of_obj(client)
                                                        == None
                                                    ):
                                                        if self.debug:
                                                            print(
                                                                "User {0} has not set their IP address, not trusting".format(
                                                                    client["id"]
                                                                )
                                                            )
                                                        if listener_detected:
                                                            self.wss.send_message(
                                                                client,
                                                                json.dumps(
                                                                    {
                                                                        "cmd": "statuscode",
                                                                        "val": self.codes[
                                                                            "IPRequred"
                                                                        ],
                                                                        "listener": listener_id,
                                                                    }
                                                                ),
                                                            )
                                                        else:
                                                            self.wss.send_message(
                                                                client,
                                                                json.dumps(
                                                                    {
                                                                        "cmd": "statuscode",
                                                                        "val": self.codes[
                                                                            "IPRequred"
                                                                        ],
                                                                    }
                                                                ),
                                                            )
                                                    else:
                                                        self.statedata[
                                                            "trusted"
                                                        ].append(client)
                                                        if self.debug:
                                                            print(
                                                                "Trusting user {0}".format(
                                                                    client["id"]
                                                                )
                                                            )

                                                        # Send the current username list.
                                                        self.wss.send_message(
                                                            client,
                                                            json.dumps(
                                                                {
                                                                    "cmd": "ulist",
                                                                    "val": self._get_ulist(),
                                                                }
                                                            ),
                                                        )

                                                        # Send the current global data stream value.
                                                        self.wss.send_message(
                                                            client,
                                                            json.dumps(
                                                                {
                                                                    "cmd": "gmsg",
                                                                    "val": str(
                                                                        self.statedata[
                                                                            "gmsg"
                                                                        ]
                                                                    ),
                                                                }
                                                            ),
                                                        )

                                                        # Tell the client it has been trusted
                                                        if listener_detected:
                                                            self.wss.send_message(
                                                                client,
                                                                json.dumps(
                                                                    {
                                                                        "cmd": "statuscode",
                                                                        "val": self.codes[
                                                                            "OK"
                                                                        ],
                                                                        "listener": listener_id,
                                                                    }
                                                                ),
                                                            )
                                                        else:
                                                            self.wss.send_message(
                                                                client,
                                                                json.dumps(
                                                                    {
                                                                        "cmd": "statuscode",
                                                                        "val": self.codes[
                                                                            "OK"
                                                                        ],
                                                                    }
                                                                ),
                                                            )
                                                else:
                                                    if listener_detected:
                                                        self.wss.send_message(
                                                            client,
                                                            json.dumps(
                                                                {
                                                                    "cmd": "statuscode",
                                                                    "val": self.codes[
                                                                        "TAInvalid"
                                                                    ],
                                                                    "listener": listener_id,
                                                                }
                                                            ),
                                                        )
                                                    else:
                                                        self.wss.send_message(
                                                            client,
                                                            json.dumps(
                                                                {
                                                                    "cmd": "statuscode",
                                                                    "val": self.codes[
                                                                        "TAInvalid"
                                                                    ],
                                                                }
                                                            ),
                                                        )
                                            else:
                                                if listener_detected:
                                                    self.wss.send_message(
                                                        client,
                                                        json.dumps(
                                                            {
                                                                "cmd": "statuscode",
                                                                "val": self.codes[
                                                                    "Datatype"
                                                                ],
                                                                "listener": listener_id,
                                                            }
                                                        ),
                                                    )
                                                else:
                                                    self.wss.send_message(
                                                        client,
                                                        json.dumps(
                                                            {
                                                                "cmd": "statuscode",
                                                                "val": self.codes[
                                                                    "Datatype"
                                                                ],
                                                            }
                                                        ),
                                                    )
                                    else:
                                        self.wss.send_message(
                                            client,
                                            json.dumps(
                                                {
                                                    "cmd": "statuscode",
                                                    "val": self.codes["Refused"],
                                                }
                                            ),
                                        )
                            else:
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["Syntax"],
                                        }
                                    ),
                                )
                        except json.decoder.JSONDecodeError:
                            if self.debug:
                                print(
                                    "Error on _on_packet_server: Failed to parse JSON"
                                )
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {"cmd": "statuscode", "val": self.codes["Syntax"]}
                                ),
                            )
                    else:
                        try:
                            msg = json.loads(message)
                            listener_detected = ("listener" in msg) and (
                                type(msg["listener"]) == str
                            )
                            listener_id = ""
                            # Support listener IDs feature from CL Turbo
                            if listener_detected:
                                listener_id = msg["listener"]
                        except:
                            listener_detected = False
                            listener_id = ""

                        def run(*args):
                            try:
                                self._server_packet_handler(
                                    client,
                                    server,
                                    message,
                                    listener_detected,
                                    listener_id,
                                )
                            except Exception as e:
                                assert self.wss is not None
                                if self.debug:
                                    print("Error on _on_packet_server: {0}".format(e))
                                self.wss.send_message(
                                    client,
                                    json.dumps(
                                        {
                                            "cmd": "statuscode",
                                            "val": self.codes["InternalServerError"],
                                        }
                                    ),
                                )

                        threading.Thread(target=run).start()
                else:

                    def run(*args):
                        assert self.wss is not None
                        try:
                            msg = json.loads(message)
                            listener_detected = ("listener" in msg) and (
                                type(msg["listener"]) == str
                            )
                            listener_id = ""
                            # Support listener IDs feature from CL Turbo
                            if listener_detected:
                                listener_id = msg["listener"]
                        except:
                            listener_detected = False
                            listener_id = ""
                        try:
                            self._server_packet_handler(
                                client, server, message, listener_detected, listener_id
                            )
                        except Exception as e:
                            if self.debug:
                                print("Error on _on_packet_server: {0}".format(e))
                            self.wss.send_message(
                                client,
                                json.dumps(
                                    {
                                        "cmd": "statuscode",
                                        "val": self.codes["InternalServerError"],
                                    }
                                ),
                            )

                    threading.Thread(target=run).start()
            except Exception as e:
                try:
                    msg = json.loads(message)
                    listener_detected = ("listener" in msg) and (
                        type(msg["listener"]) == str
                    )
                    listener_id = ""
                    # Support listener IDs feature from CL Turbo
                    if listener_detected:
                        listener_id = msg["listener"]
                except:
                    listener_detected = False
                    listener_id = ""
                if self.debug:
                    print("Error on _on_packet_server: {0}".format(e))
                if listener_detected:
                    self.wss.send_message(
                        client,
                        json.dumps(
                            {
                                "cmd": "statuscode",
                                "val": self.codes["InternalServerError"],
                                "listener": listener_id,
                            }
                        ),
                    )
                else:
                    self.wss.send_message(
                        client,
                        json.dumps(
                            {
                                "cmd": "statuscode",
                                "val": self.codes["InternalServerError"],
                            }
                        ),
                    )

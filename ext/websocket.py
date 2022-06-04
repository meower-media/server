from websocket_server import WebsocketServer
from threading import Thread
import json
import time

class WS:
    def server(self, meower):
        self.meower = meower
        self.log = meower.log

        # Create WebSocket Server
        self.ws_host = "127.0.0.1"
        self.ws_port = 3000
        self.wss = WebsocketServer(
            host=self.ws_host, 
            port=self.ws_port
        )

        # Register callbacks
        self.wss.set_fn_new_client(self._on_connect)
        self.wss.set_fn_client_left(self._on_disconnect)
        self.wss.set_fn_message_received(self._on_packet)

        # Register statuscodes
        self.statuscodes = {
            "OK": "I:100 | OK",
            "Syntax": "E:101 | Syntax",
            "Datatype": "E:102 | Datatype",
            "TooLarge": "E:103 | Packet too large",
            "Internal": "E:104 | Internal",
            "InvalidToken": "E:106 | Invalid token",
            "Refused": "E:107 | Refused",
            "IDNotFound": "E:108 | ID not found",
            "RateLimit": "E:109 | Too many requests",
            "Disabled": "E:110 | Command disabled by sysadmin",
        }

        # Create users list and login codes objects
        self.ulist = {}
        self.tokens = {}
        self.login_codes = {}

        # Create peak users object
        file_read, payload = self.meower.files.load_item("config", "peak_users")
        if file_read:
            self.peak_users = payload
            del self.peak_users["_id"]
        else:
            self.peak_users = {
                "count": 0,
                "timestamp": self.meower.timestamp(1)
            }

        # Start server
        self.log("Running server on port ws://{0}:{1}".format(self.ws_host, self.ws_port), prefix="WS")
        self.wss.run_forever()

    def setUser(self, client, user):
        if client["user"] is None:
            client["user"] = user
            if not (user in self.ulist):
                self.ulist[user] = []
            self.ulist[user].append(client)

    def abruptLogout(self, client=None, user=None, token=None):
        def run(client, user):
            if client is not None:
                self.log("Kicking client: {0}".format(client["id"]), prefix="WS")
                self.sendPayload("abrupt_logout", "", client=client)
                time.sleep(0.5)
                self.wss.close_request(client)
            elif user is not None:
                if user in self.ulist:
                    for client in self.ulist[user]:
                        self.log("Kicking client: {0}".format(client["id"]), prefix="WS")
                        try:
                            self.sendPayload("abrupt_logout", "", client=client)
                            time.sleep(0.5)
                            self.wss.close_request(client)
                        except:
                            pass
            elif token is not None:
                if token in self.tokens:
                    for client in self.tokens[token]:
                        self.log("Kicking client: {0}".format(client["id"]), prefix="WS")
                        try:
                            self.sendPayload("abrupt_logout", "", client=client)
                            time.sleep(0.5)
                            self.wss.close_request(client)
                        except:
                            pass
            else:
                self.log("Kicking all clients", prefix="WS")
                self.sendPayload("abrupt_logout", "")
                time.sleep(0.5)
                self.wss.disconnect_clients_abruptly()

        Thread(target=run, args=(client,user,)).start()

    def sendPacket(self, packet, client=None, user=None, listener=None):
        try:
            if listener is not None:
                packet["listener"] = listener
            packet = json.dumps(packet)
        except:
            self.log("Error: Invalid JSON packet", prefix="WS")
            return

        if client is not None:
            self.log("Sending packet to: {0}".format(client["id"]), prefix="WS")
            self.wss.send_message(client, packet)
        elif user is not None:
            if user in self.ulist:
                for client in self.ulist[user]:
                    self.log("Sending packet to: {0}".format(client["id"]), prefix="WS")
                    self.wss.send_message(client, packet)
        else:
            self.log("Sending packet to all clients", prefix="WS")
            self.wss.send_message_to_all(packet)

    def sendStatus(self, client, status, listener=None):
        self.sendPacket({"cmd": "statuscode", "val": self.statuscodes[status]}, client=client, listener=listener)

    def sendUlist(self, client=None, listener=None):
        parsed_ulist = []
        for user in self.ulist.keys():
            file_read, userdata = self.meower.accounts.get_account(user)
            if file_read:
                if not ((userdata["userdata"]["user_status"] == "Offline")):
                    parsed_ulist.append(user)
        self.sendPacket({"cmd": "ulist", "val": parsed_ulist}, client=client, listener=listener)

    def sendPayload(self, mode, data, client=None, user=None, listener=None):
        payload = {
            "mode": mode,
            "payload": data
        }
        self.sendPacket({"cmd": "direct", "val": payload}, client=client, user=user, listener=listener)

    def updatePeakUsers(self):
        if len(list(self.ulist.keys())) > self.peak_users["count"]:
            self.peak_users["count"] = len(list(self.ulist.keys()))
            self.peak_users["timestamp"] = self.meower.timestamp(1)
            self.sendPayload("peak", self.peak_users)

    def _on_connect(self, client, server):
        client["user"] = None
        if self.meower.repair_mode:
            self.log("Repair mode is enabled! Refusing new connection: {0}".format(client["id"], prefix="WS"))
            self.wss.disconnect_clients_abruptly()
        else:
            self.log("New Connection: {0}".format(client["id"]), prefix="WS")
            self.sendUlist(client=client)

    def _on_disconnect(self, client, server):
        self.log("Disconnected: {0}".format(client["id"]), prefix="WS")
        if client["user"] in self.ulist:
            self.ulist[client["user"]].remove(client)
            if len(self.ulist[client["user"]]) == 0:
                del self.ulist[client["user"]]
                file_read, userdata = self.meower.accounts.get_account(client["user"])
                if file_read:
                    if userdata["userdata"]["user_status"] != "Offline":
                        self.meower.accounts.update_config(client["user"], {"last_seen": self.meower.timestamp(6)}, forceUpdate=True)
            self.sendUlist()

    def _on_packet(self, client, server, packet):
        def run(client, server, packet):
            try:
                packet = json.loads(packet)
            except:
                self.log("Error: Invalid JSON packet", prefix="WS")
                return self.sendStatus(client, "Datatype")
            
            if not ("cmd" in packet and "val" in packet):
                self.log("Error: Invalid packet", prefix="WS")
                return self.sendStatus(client, "Syntax")

            self.log("Handling '{0}' from: {1}".format(packet["cmd"], client["id"]), prefix="WS")

            if not ("listener" in packet):
                packet["listener"] = None

            cmd = packet["cmd"]
            val = packet["val"]
            listener = packet["listener"]
            auth = client["user"]

            if cmd == "ping":
                self.sendStatus(client, "OK", listener=listener)
                return
            elif cmd == "ulist":
                self.sendUlist(client=client, listener=listener)
                return
            elif cmd == "get_peak_users":
                if auth is None:
                    # Client not authenticated
                    return self.sendStatus(client, "Refused", listener=listener)
                return self.sendPayload("peak", self.peak_users, client=client, listener=listener)
            elif cmd == "auth":
                if auth != None:
                    # Client already authenticated
                    return self.sendStatus(client, "OK", listener=listener)
                elif type(val) != str:
                    # Token not correct datatype
                    return self.sendStatus(client, "Datatype", listener=listener)
                elif len(val) > 100:
                    # Token too large
                    return self.sendStatus(client, "TooLarge", listener=listener)

                file_read, token_data = self.meower.accounts.get_token(val)
                if not file_read or (token_data["type"] != 1):
                    # Token not found
                    return self.sendStatus(client, "InvalidToken", listener=listener)

                # Authenticate client
                self.setUser(client, token_data["user"])

                # Return payload to client
                self.sendPayload("auth", {"user_id": token_data["user"]}, client=client, listener=listener)
                self.sendStatus(client, "OK", listener=listener)
                self.sendUlist()
                return
            elif cmd == "get_profile":
                if auth is None:
                    # Client not authenticated
                    return self.sendStatus(client, "Refused", listener=listener)
                elif type(val) != str:
                    # Token not correct datatype
                    return self.sendStatus(client, "Datatype", listener=listener)
                elif len(val) > 20:
                    # Token too large
                    return self.sendStatus(client, "TooLarge", listener=listener)

                file_read, userdata = self.meower.accounts.get_account(val)
                if not file_read:
                    # User not found
                    return self.sendStatus(client, "IDNotFound", listener=listener)

                self.sendPayload("profile", userdata["profile"], client=client, listener=listener)
                self.sendStatus(client, "OK", listener=listener)
                return
            elif cmd == "set_status":
                if auth is None:
                    # Client not authenticated
                    return self.sendStatus(client, "Refused", listener=listener)
                elif type(val) != int:
                    # Token not correct datatype
                    return self.sendStatus(client, "Datatype", listener=listener)
                elif len(val) > 20:
                    # Token too large
                    return self.sendStatus(client, "TooLarge", listener=listener)
                elif not (val in ["Offline", "Online", "Away", "Do Not Disturb"]):
                    # Invalid status
                    return self.sendStatus(client, "Refused", listener=listener)
                
                self.meower.accounts.update_config(auth, {"user_status": val}, forceUpdate=True)
                self.sendPayload("user_status", {"user": auth, "status": val}, client=client, listener=listener)
                self.sendStatus(client, "OK", listener=listener)
                return
        
        Thread(target=run, args=(client,server,packet,)).start()
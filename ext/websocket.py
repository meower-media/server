from websocket_server import WebsocketServer
from threading import Thread
import json

class WS:
    def __init__(self, meower):
        self.meower = meower

    def server(self):
        # Create WebSocket Server
        self.wss = WebsocketServer(
            host="127.0.0.1", 
            port=3000
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
        self.login_codes = {}

        # Create peak users object
        file_read, payload = self.meower.files.load_item("config", "peak_users")
        if file_read:
            self.peak_users = payload
            del self.peak_users["_id"]
        else:
            self.peak_users = {
                "count": 0,
                "timestamp": self.meower.supporter.timestamp(1)
            }

        # Start server
        print("[WS] Starting server...")
        self.wss.run_forever()

    def setUsername(self, client, username):
        if client["username"] is None:
            client["username"] = username
            if not (username in self.ulist):
                self.ulist[username] = []
            self.ulist[username].append(client)

    def sendPacket(self, packet, client=None, username=None, listener=None):
        try:
            if listener is not None:
                packet["listener"] = listener
            packet = json.dumps(packet)
        except:
            print("[WS] Error: Invalid JSON packet")
            return

        if client is not None:
            print("[WS] Sending packet to: {0}".format(client["id"]))
            self.wss.send_message(client, packet)
        elif username is not None:
            if username in self.ulist:
                for client in self.ulist[username]:
                    print("[WS] Sending packet to: {0}".format(client["id"]))
                    self.wss.send_message(client, packet)
        else:
            print("[WS] Sending packet to all clients")
            self.wss.send_message_to_all(packet)

    def sendStatus(self, client, status, listener=None):
        self.sendPacket({"cmd": "statuscode", "val": self.statuscodes[status]}, client=client, listener=listener)

    def sendUlist(self, client=None, listener=None):
        self.sendPacket({"cmd": "ulist", "val": list(self.ulist.keys())}, client=client, listener=listener)

    def sendPayload(self, mode, data, client=None, username=None, listener=None):
        payload = {
            "mode": mode,
            "payload": data
        }
        self.sendPacket({"cmd": "direct", "val": payload}, client=client, username=username, listener=listener)

    def updatePeakUsers(self):
        if len(list(self.ulist.keys())) > self.peak_users["count"]:
            self.peak_users["count"] = len(list(self.ulist.keys()))
            self.peak_users["timestamp"] = self.meower.supporter.timestamp(1)
            self.sendPayload("peak", self.peak_users)

    def _on_connect(self, client, server):
        print("[WS] New Connection: {0}".format(client["id"]))
        client["username"] = None
        self.sendUlist(client=client)

    def _on_disconnect(self, client, server):
        print("[WS] Disconnected: {0}".format(client["id"]))
        if client["username"] in self.ulist:
            self.ulist[client["username"]].remove(client)
            if len(self.ulist[client["username"]]) == 0:
                del self.ulist[client["username"]]
            file_read, userdata = self.meower.accounts.get_account(client["username"])
            if file_read:
                if userdata["userdata"]["user_status"] != "Offline":
                    self.meower.accounts.update_config(client["username"], {"last_seen": self.meower.supporter.timestamp(6)}, forceUpdate=True)
        self.sendUlist()

    def _on_packet(self, client, server, packet):
        def run(client, server, packet):
            try:
                packet = json.loads(packet)
            except:
                print("[WS] Error: Invalid JSON packet")
                return self.sendStatus(client, "Datatype")
            
            if not ("cmd" in packet and "val" in packet):
                print("[WS] Error: Invalid packet")
                return self.sendStatus(client, "Syntax")

            print("[WS] Handling '{0}' from: {1}".format(packet["cmd"], client["id"]))

            if not ("listener" in packet):
                packet["listener"] = None

            cmd = packet["cmd"]
            val = packet["val"]
            listener = packet["listener"]
            auth = client["username"]

            if cmd == "ping":
                self.sendStatus(client, "OK", listener=listener)
                return
            elif cmd == "ulist":
                self.sendUlist(client=client, listener=listener)
                return
            elif cmd == "get_peak_users":
                if auth == None:
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
                self.setUsername(client, token_data["u"])

                # Return payload to client
                self.sendPayload("auth", {"username": token_data["u"]}, client=client, listener=listener)
                self.sendStatus(client, "OK", listener=listener)
                self.sendUlist()
                return
            elif cmd == "get_profile":
                if auth == None:
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
                if auth == None:
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
                self.sendPayload("user_status", {"username": auth, "status": val}, client=client, listener=listener)
                self.sendStatus(client, "OK", listener=listener)
                return
        
        Thread(target=run, args=(client,server,packet,)).start()
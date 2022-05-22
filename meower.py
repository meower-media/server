from threading import Thread

class Meower:
    def __init__(self):
        # Set server MOTD
        self.cl.setMOTD("Meower Social Media Platform Server - v{0}".format(self.version), True)

        # Load trust keys
        FileRead, payload = self.files.load_item("config", "trust_keys")
        if FileRead:
            self.cl.trustedAccess(True, payload["index"])
        
        # Load IP Banlist
        FileRead, payload = self.files.load_item("config", "IPBanlist")
        if FileRead:
            self.cl.loadIPBlocklist(payload["wildcard"])
        
        # Load profanity filter
        FileRead, payload = self.files.load_item("config", "filter")
        if FileRead:
            self.supporter.profanity.load_censor_words(whitelist_words=payload["whitelist"])
            self.supporter.profanity.add_censor_words(custom_words=payload["blacklist"])

        # Set repair status
        FileRead, payload = self.files.load_item("config", "status")
        if FileRead:
            self.supporter.repair_mode = payload["repair_mode"]
            self.supporter.is_deprecated = payload["is_deprecated"]

        # Start CL server
        self.cl_server = Thread(target=self.cl.server, kwargs={"ip": "0.0.0.0", "port": 3000})
        self.cl_server.start()

        # Start REST API
        self.rest_api_app = Thread(target=self.rest_api, args=(self,), kwargs={"ip": "0.0.0.0", "port": 3001})
        self.rest_api_app.start()

    def run_ws_command(self, cmd, val, listener_detected, listener_id, client):
        try:
            commands = [
                "ping",
                "version_chk",
                "authpswd",
                "gen_account",
                "get_profile",
                "update_config",
                "del_account",
                "get_home",
                "get_inbox",
                "post_home",
                "get_post",
                "get_peak_users",
                "search_user_posts",
                "search_home_posts",
                "search_profiles",
                "clear_home",
                "alert",
                "announce",
                "block",
                "unblock",
                "kick",
                "get_user_ip",
                "get_ip_data",
                "get_user_data",
                "ban",
                "pardon",
                "ip_ban",
                "ip_pardon",
                "terminate",
                "repair_mode",
                "delete_post",
                "post_chat",
                "set_chat_state",
                "create_chat",
                "leave_chat",
                "get_chat_list",
                "get_chat_data",
                "get_chat_posts",
                "add_to_chat",
                "remove_from_chat",
                "transfer_ownership"
            ]
            if (type(cmd) == str) and (cmd in commands):
                cmd_function = getattr(self.commands, cmd)
                cmd_function(client, val, listener_detected, listener_id)
            else:
                # Catch-all error code
                self.commands.returnCode(code = "Invalid", client = client, listener_detected = listener_detected, listener_id = listener_id)
        except:
            self.supporter.log(self.supporter.full_stack())

    def restart_services(self):
        self.cl_server.stop()
        self.rest_api_app.stop()
        self.__init__()
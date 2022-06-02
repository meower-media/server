class Chats:
    def __init__(self, meower):
        self.meower = meower
        self.log = self.meower.supporter.log

        self.log("Chats initialized!")
    
    def has_permission(self, chatid, user):
        if (chatid == "home") or (chatid == "livechat"):
            return True
        FileRead, chatdata = self.meower.files.load_item("chats", chatid)
        if not FileRead:
            return False
        return (user in chatdata["members"])

    def get_members_list(self, chatid):
        if (chatid == "home") or (chatid == "livechat"):
            return self.cl.getUsernames()
        FileRead, chatdata = self.meower.files.load_item("chats", chatid)
        if not FileRead:
            return FileRead, None
        return FileRead, chatdata["members"]